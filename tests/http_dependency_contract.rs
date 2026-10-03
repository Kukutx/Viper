//! Exercise the production HTTP factories using private loopback endpoints only.
#![cfg(target_os = "linux")]
#[path = "../src/hbbs_http/http_client.rs"]
mod http_client;

use hbb_common::{
    config::{self, Config, Socks5Server},
    tls::{self, TlsType},
};
use openssl::ssl::{select_next_proto, AlpnError, SslAcceptor, SslFiletype, SslMethod};
use std::{
    collections::BTreeMap,
    io::{Read, Write},
    net::{SocketAddr, TcpListener, TcpStream},
    path::PathBuf,
    sync::{atomic::{AtomicBool, Ordering}, Arc, Mutex},
    thread::{self, JoinHandle},
    time::Duration,
};

const BODY: &[u8] = b"{\"message\":\"http-contract\"}";
const TIMEOUT: Duration = Duration::from_secs(5);

struct Isolation;
impl Isolation {
    fn new() -> Self {
        let fixture = fixture();
        assert_eq!(PathBuf::from(std::env::var_os("HOME").unwrap()), fixture.join("home"));
        assert!(std::env::args().any(|arg| arg == "--test-threads=1"));
        Config::set_socks(None);
        Config::set_option(config::keys::OPTION_ALLOW_INSECURE_TLS_FALLBACK.into(), "N".into());
        tls::reset_tls_cache();
        Self
    }
}
impl Drop for Isolation {
    fn drop(&mut self) {
        Config::set_socks(None);
        Config::set_option(config::keys::OPTION_ALLOW_INSECURE_TLS_FALLBACK.into(), "N".into());
        tls::reset_tls_cache();
    }
}
fn fixture() -> PathBuf {
    PathBuf::from(std::env::var_os("VIPER_HTTP_TEST_DIR").expect("run tools/native/test-http.sh"))
}

#[derive(Clone, Debug)]
struct Request {
    method: String,
    target: String,
    headers: BTreeMap<String, String>,
    body: Vec<u8>,
}
fn read_request(stream: &mut (impl Read + ?Sized)) -> std::io::Result<Request> {
    let mut head = Vec::new();
    while !head.ends_with(b"\r\n\r\n") {
        assert!(head.len() < 16384, "unbounded request headers");
        let mut byte = [0];
        stream.read_exact(&mut byte)?;
        head.push(byte[0]);
    }
    let head = String::from_utf8(head).unwrap();
    let mut lines = head.split("\r\n");
    let mut request_line = lines.next().unwrap().split_whitespace();
    let method = request_line.next().unwrap().to_string();
    let target = request_line.next().unwrap().to_string();
    let headers: BTreeMap<_, _> = lines.filter_map(|line| line.split_once(':'))
        .map(|(name, value)| (name.to_ascii_lowercase(), value.trim().to_string())).collect();
    let length: usize = headers.get("content-length").map(|s| s.parse().unwrap()).unwrap_or(0);
    assert!(length <= 1048576);
    let mut body = vec![0; length];
    stream.read_exact(&mut body)?;
    Ok(Request { method, target, headers, body })
}
fn response(status: &str, headers: &str, body: &[u8]) -> Vec<u8> {
    let mut value = format!("HTTP/1.1 {status}\r\nContent-Length: {}\r\nConnection: close\r\n{headers}\r\n", body.len()).into_bytes();
    value.extend_from_slice(body);
    value
}
fn ok_response() -> Vec<u8> { response("200 OK", "Content-Type: application/json\r\n", BODY) }

struct Server {
    addr: SocketAddr,
    requests: Arc<Mutex<Vec<Request>>>,
    stop: Arc<AtomicBool>,
    thread: Option<JoinHandle<()>>,
}
impl Server {
    fn new(certificate: Option<&str>, socks: bool, reply: Vec<u8>) -> Self {
        let require_alpn = certificate == Some("alpn");
        let tls = certificate.map(|name| {
            let name = if require_alpn { "trusted" } else { name };
            let mut builder = SslAcceptor::mozilla_intermediate(SslMethod::tls_server()).unwrap();
            builder.set_certificate_chain_file(fixture().join(format!("{name}.pem"))).unwrap();
            builder.set_private_key_file(fixture().join("server.key"), SslFiletype::PEM).unwrap();
            builder.check_private_key().unwrap();
            if require_alpn {
                builder.set_alpn_select_callback(|_, offered| {
                    select_next_proto(b"\x08http/1.1", offered).ok_or(AlpnError::ALERT_FATAL)
                });
            }
            builder.build()
        });
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let addr = listener.local_addr().unwrap();
        listener.set_nonblocking(true).unwrap();
        let stop = Arc::new(AtomicBool::new(false));
        let requests = Arc::new(Mutex::new(Vec::new()));
        let (stopped, observed) = (stop.clone(), requests.clone());
        let thread = thread::spawn(move || {
            while !stopped.load(Ordering::Acquire) {
                let (mut stream, _) = match listener.accept() {
                    Ok(value) => value,
                    Err(error) if error.kind() == std::io::ErrorKind::WouldBlock => {
                        thread::sleep(Duration::from_millis(2));
                        continue;
                    }
                    Err(error) => panic!("loopback accept failed: {error}"),
                };
                stream.set_read_timeout(Some(TIMEOUT)).unwrap();
                stream.set_write_timeout(Some(TIMEOUT)).unwrap();
                if socks { socks_handshake(&mut stream); }
                let serve = |stream: &mut dyn ReadWrite| {
                    if let Ok(request) = read_request(stream) {
                        let is_head = request.method == "HEAD";
                        observed.lock().unwrap().push(request);
                        let bytes = if is_head {
                            let end = reply.windows(4).position(|x| x == b"\r\n\r\n").unwrap() + 4;
                            &reply[..end]
                        } else { &reply[..] };
                        stream.write_all(bytes).unwrap();
                        stream.flush().unwrap();
                    }
                };
                if let Some(acceptor) = &tls {
                    // Certificate-rejection cases deliberately terminate the handshake.
                    if let Ok(mut encrypted) = acceptor.accept(stream) {
                        if require_alpn {
                            assert_eq!(encrypted.ssl().selected_alpn_protocol(), Some(&b"http/1.1"[..]));
                        }
                        serve(&mut encrypted);
                    }
                } else { serve(&mut stream); }
            }
        });
        Self { addr, stop, requests, thread: Some(thread) }
    }
    fn url(&self, scheme: &str) -> String { format!("{scheme}://127.0.0.1:{}/contract", self.addr.port()) }
    fn requests(&self) -> Vec<Request> { self.requests.lock().unwrap().clone() }
}
impl Drop for Server {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::Release);
        self.thread.take().unwrap().join().unwrap();
    }
}
trait ReadWrite: Read + Write {}
impl<T: Read + Write> ReadWrite for T {}

fn socks_handshake(stream: &mut TcpStream) {
    let mut hello = [0; 2];
    stream.read_exact(&mut hello).unwrap();
    assert_eq!(hello[0], 5);
    let mut methods = vec![0; hello[1] as usize];
    stream.read_exact(&mut methods).unwrap();
    assert!(methods.contains(&2));
    stream.write_all(&[5, 2]).unwrap();
    let mut auth = [0; 2];
    stream.read_exact(&mut auth).unwrap();
    assert_eq!(auth[0], 1);
    let mut username = vec![0; auth[1] as usize];
    stream.read_exact(&mut username).unwrap();
    let mut length = [0];
    stream.read_exact(&mut length).unwrap();
    let mut password = vec![0; length[0] as usize];
    stream.read_exact(&mut password).unwrap();
    assert_eq!(username, b"test-user");
    assert_eq!(password, b"test-pass");
    stream.write_all(&[1, 0]).unwrap();
    let mut connect = [0; 4];
    stream.read_exact(&mut connect).unwrap();
    assert_eq!(connect, [5, 1, 0, 1]);
    let mut destination = [0; 6];
    stream.read_exact(&mut destination).unwrap();
    assert_eq!(&destination[..4], &[127, 0, 0, 1]);
    stream.write_all(&[5, 0, 0, 1, 127, 0, 0, 1, 0, 80]).unwrap();
}
fn set_proxy(server: &Server, scheme: &str) {
    Config::set_socks(Some(Socks5Server {
        proxy: format!("{scheme}://{}", server.addr),
        username: "test-user".into(), password: "test-pass".into(),
    }));
}

#[test]
fn synchronous_json_query_and_binary_upload_preserve_wire_bytes() {
    let _isolation = Isolation::new();
    let server = Server::new(None, false, ok_response());
    let client = http_client::create_http_client(TlsType::Plain, false).unwrap();
    let body = vec![0, 1, 127, 128, 255];
    let answer: serde_json::Value = client.post(server.url("http"))
        .query(&[("filename", "record +&/中文")]).body(body.clone()).timeout(TIMEOUT)
        .send().unwrap().json().unwrap();
    assert_eq!(answer["message"], "http-contract");
    let requests = server.requests();
    assert_eq!(requests.len(), 1);
    assert_eq!(requests[0].method, "POST");
    assert_eq!(requests[0].body, body);
    let url = url::Url::parse(&format!("http://localhost{}", requests[0].target)).unwrap();
    assert_eq!(url.query_pairs().next().unwrap().1, "record +&/中文");
    client.post(server.url("http")).json(&answer).timeout(TIMEOUT).send().unwrap();
    let requests = server.requests();
    assert_eq!(requests[1].headers["content-type"], "application/json");
    assert_eq!(serde_json::from_slice::<serde_json::Value>(&requests[1].body).unwrap(), answer);
}

#[tokio::test]
async fn asynchronous_json_query_ignores_ambient_proxies() {
    let _isolation = Isolation::new();
    let server = Server::new(None, false, ok_response());
    let client = http_client::create_http_client_async(TlsType::Plain, false).unwrap();
    let answer: serde_json::Value = client.post(server.url("http"))
        .query(&[("name", "a +&")]).json(&serde_json::json!({"hello": "中文"})).timeout(TIMEOUT)
        .send().await.unwrap().json().await.unwrap();
    assert_eq!(answer["message"], "http-contract");
    let requests = server.requests();
    assert_eq!(requests.len(), 1);
    assert_eq!(requests[0].headers["content-type"], "application/json");
    assert_eq!(serde_json::from_slice::<serde_json::Value>(&requests[0].body).unwrap()["hello"], "中文");
    let url = url::Url::parse(&format!("http://localhost{}", requests[0].target)).unwrap();
    assert_eq!(url.query_pairs().next().unwrap().1, "a +&");
}

#[test]
fn synchronous_tls_checks_trust_and_hostname_for_both_backends() {
    let _isolation = Isolation::new();
    for backend in [TlsType::NativeTls, TlsType::Rustls] {
        for name in ["trusted", "untrusted", "wrong-host"] {
            let server = Server::new(Some(name), false, ok_response());
            let result = http_client::create_http_client(backend, false).unwrap().get(server.url("https"))
                .timeout(TIMEOUT).send();
            if name == "trusted" { assert_eq!(result.unwrap().text().unwrap().as_bytes(), BODY); }
            else { assert!(result.is_err(), "{backend:?} accepted {name}"); }
        }
    }
}

#[tokio::test]
async fn asynchronous_tls_checks_trust_and_hostname_for_both_backends() {
    let _isolation = Isolation::new();
    for backend in [TlsType::NativeTls, TlsType::Rustls] {
        for name in ["trusted", "untrusted", "wrong-host"] {
            let server = Server::new(Some(name), false, ok_response());
            let result = http_client::create_http_client_async(backend, false).unwrap().get(server.url("https"))
                .timeout(TIMEOUT).send().await;
            if name == "trusted" { assert_eq!(result.unwrap().text().await.unwrap().as_bytes(), BODY); }
            else { assert!(result.is_err(), "{backend:?} accepted {name}"); }
        }
    }
}

#[test]
fn explicit_insecure_opt_in_remains_explicit() {
    let _isolation = Isolation::new();
    let server = Server::new(Some("untrusted"), false, ok_response());
    for backend in [TlsType::NativeTls, TlsType::Rustls] {
        assert!(http_client::create_http_client(backend, false).unwrap().get(server.url("https")).timeout(TIMEOUT).send().is_err());
        assert_eq!(http_client::create_http_client(backend, true).unwrap().get(server.url("https")).timeout(TIMEOUT).send().unwrap().status(), 200);
    }
}

#[test]
fn strict_sync_factory_never_inherits_an_insecure_cached_probe() {
    let _isolation = Isolation::new();
    assert!(http_client::create_http_client_with_url_strict("http://127.0.0.1:9").is_err());
    Config::set_option(config::keys::OPTION_ALLOW_INSECURE_TLS_FALLBACK.into(), "Y".into());
    let server = Server::new(Some("untrusted"), false, ok_response());
    let url = server.url("https");
    tls::upsert_tls_cache(&url, TlsType::Rustls, true);
    assert_eq!(tls::get_cached_tls_accept_invalid_cert(&url), Some(true));
    let client = http_client::create_http_client_with_url_strict(&url).unwrap();
    assert!(client.get(&url).timeout(TIMEOUT).send().is_err());
    assert!(server.requests().is_empty());
}

#[tokio::test]
async fn strict_async_factory_never_inherits_an_insecure_cached_probe() {
    let _isolation = Isolation::new();
    assert!(http_client::create_http_client_async_with_url_strict("http://127.0.0.1:9").await.is_err());
    Config::set_option(config::keys::OPTION_ALLOW_INSECURE_TLS_FALLBACK.into(), "Y".into());
    let server = Server::new(Some("untrusted"), false, ok_response());
    let url = server.url("https");
    tls::upsert_tls_cache(&url, TlsType::Rustls, true);
    assert_eq!(tls::get_cached_tls_accept_invalid_cert(&url), Some(true));
    let client = http_client::create_http_client_async_with_url_strict(&url).await.unwrap();
    assert!(client.get(&url).timeout(TIMEOUT).send().await.is_err());
    assert!(server.requests().is_empty());
}

#[test]
fn automatic_sync_tls_probe_keeps_certificate_validation_strict_by_default() {
    let _isolation = Isolation::new();
    let server = Server::new(Some("untrusted"), false, ok_response());
    let url = server.url("https");
    let client = http_client::create_http_client_with_url(&url).unwrap();
    assert!(client.get(&url).timeout(TIMEOUT).send().is_err());
    assert_ne!(tls::get_cached_tls_accept_invalid_cert(&url), Some(true));
}

#[tokio::test]
async fn automatic_async_tls_probe_keeps_certificate_validation_strict_by_default() {
    let _isolation = Isolation::new();
    let server = Server::new(Some("untrusted"), false, ok_response());
    let url = server.url("https");
    let client = http_client::create_http_client_async_with_url(&url).await.unwrap();
    assert!(client.get(&url).timeout(TIMEOUT).send().await.is_err());
    assert_ne!(tls::get_cached_tls_accept_invalid_cert(&url), Some(true));
}

#[test]
fn insecure_tls_probe_requires_explicit_configuration() {
    let _isolation = Isolation::new();
    Config::set_option(config::keys::OPTION_ALLOW_INSECURE_TLS_FALLBACK.into(), "Y".into());
    let server = Server::new(Some("untrusted"), false, ok_response());
    let url = server.url("https");
    let client = http_client::create_http_client_with_url(&url).unwrap();
    assert_eq!(client.get(&url).timeout(TIMEOUT).send().unwrap().status(), 200);
    assert_eq!(tls::get_cached_tls_accept_invalid_cert(&url), Some(true));
}

#[test]
fn synchronous_http_https_and_socks5_proxies_keep_authentication() {
    let _isolation = Isolation::new();
    for scheme in ["http", "https", "socks5"] {
        let server = Server::new((scheme == "https").then_some("trusted"), scheme == "socks5", ok_response());
        set_proxy(&server, scheme);
        let client = http_client::create_http_client(TlsType::Rustls, false).unwrap();
        assert_eq!(client.get("http://127.0.0.1:9/proxied").timeout(TIMEOUT).send().unwrap().status(), 200);
        let requests = server.requests();
        assert_eq!(requests.len(), 1);
        if scheme != "socks5" {
            assert_eq!(requests[0].target, "http://127.0.0.1:9/proxied");
            assert_eq!(requests[0].headers["proxy-authorization"], "Basic dGVzdC11c2VyOnRlc3QtcGFzcw==");
        } else { assert!(!requests[0].headers.contains_key("proxy-authorization")); }
    }
}

#[tokio::test]
async fn asynchronous_http_https_and_socks5_proxies_keep_authentication() {
    let _isolation = Isolation::new();
    for scheme in ["http", "https", "socks5"] {
        let server = Server::new((scheme == "https").then_some("trusted"), scheme == "socks5", ok_response());
        set_proxy(&server, scheme);
        let client = http_client::create_http_client_async(TlsType::Rustls, false).unwrap();
        assert_eq!(client.get("http://127.0.0.1:9/proxied").timeout(TIMEOUT).send().await.unwrap().status(), 200);
        let requests = server.requests();
        assert_eq!(requests.len(), 1);
        if scheme != "socks5" {
            assert_eq!(requests[0].target, "http://127.0.0.1:9/proxied");
            assert_eq!(requests[0].headers["proxy-authorization"], "Basic dGVzdC11c2VyOnRlc3QtcGFzcw==");
        } else { assert!(!requests[0].headers.contains_key("proxy-authorization")); }
    }
}

#[test]
fn invalid_explicit_proxy_configuration_never_falls_back_to_direct_sync() {
    let _isolation = Isolation::new();
    Config::set_socks(Some(Socks5Server {
        proxy: "http://[".into(),
        username: String::new(),
        password: String::new(),
    }));
    assert!(http_client::create_http_client(TlsType::Rustls, false).is_err());
}

#[test]
fn invalid_explicit_proxy_configuration_never_falls_back_to_direct_async() {
    let _isolation = Isolation::new();
    Config::set_socks(Some(Socks5Server {
        proxy: "socks5://[".into(),
        username: String::new(),
        password: String::new(),
    }));
    assert!(http_client::create_http_client_async(TlsType::Rustls, false).is_err());
}

fn compressed_reply(encoding: &str) -> Vec<u8> {
    let bytes = match encoding {
        "gzip" => std::fs::read(fixture().join("body.gz")).unwrap(),
        "zstd" => zstd::encode_all(BODY, 1).unwrap(),
        _ => unreachable!(),
    };
    response("200 OK", &format!("Content-Encoding: {encoding}\r\n"), &bytes)
}
#[test]
fn synchronous_gzip_and_zstd_decode_without_stale_content_length() {
    let _isolation = Isolation::new();
    for encoding in ["gzip", "zstd"] {
        let server = Server::new(None, false, compressed_reply(encoding));
        let response = http_client::create_http_client(TlsType::Plain, false).unwrap().get(server.url("http"))
            .timeout(TIMEOUT).send().unwrap();
        assert!(response.headers().get("content-length").is_none());
        assert_eq!(&response.bytes().unwrap()[..], BODY);
        assert!(server.requests()[0].headers["accept-encoding"].contains(encoding));
    }
}
#[tokio::test]
async fn asynchronous_gzip_and_zstd_decode_without_stale_content_length() {
    let _isolation = Isolation::new();
    for encoding in ["gzip", "zstd"] {
        let server = Server::new(None, false, compressed_reply(encoding));
        let response = http_client::create_http_client_async(TlsType::Plain, false).unwrap().get(server.url("http"))
            .timeout(TIMEOUT).send().await.unwrap();
        assert!(response.headers().get("content-length").is_none());
        assert_eq!(&response.bytes().await.unwrap()[..], BODY);
        assert!(server.requests()[0].headers["accept-encoding"].contains(encoding));
    }
}

#[test]
fn redirects_strip_credentials_across_origins() {
    let _isolation = Isolation::new();
    let destination = Server::new(None, false, ok_response());
    let redirect = Server::new(None, false, response("302 Found", &format!("Location: {}\r\n", destination.url("http")), b""));
    let response = http_client::create_http_client(TlsType::Plain, false).unwrap().get(redirect.url("http"))
        .bearer_auth("test-only-token").header("cookie", "test-only-cookie=1").timeout(TIMEOUT).send().unwrap();
    assert_eq!(response.status(), 200);
    assert_eq!(redirect.requests()[0].headers["authorization"], "Bearer test-only-token");
    let requests = destination.requests();
    assert!(!requests[0].headers.contains_key("authorization"));
    assert!(!requests[0].headers.contains_key("cookie"));
}

#[test]
fn streaming_download_length_status_and_error_propagation_are_preserved() {
    let _isolation = Isolation::new();
    let bytes: Vec<u8> = (0..=255).cycle().take(32768).collect();
    let server = Server::new(None, false, response("200 OK", "", &bytes));
    let client = http_client::create_http_client(TlsType::Plain, false).unwrap();
    let mut answer = client.get(server.url("http")).timeout(TIMEOUT).send().unwrap();
    assert_eq!(answer.content_length(), Some(bytes.len() as u64));
    let mut downloaded = Vec::new();
    answer.read_to_end(&mut downloaded).unwrap();
    assert_eq!(downloaded, bytes);
    let missing = Server::new(None, false, response("404 Not Found", "", b"missing"));
    assert_eq!(client.get(missing.url("http")).timeout(TIMEOUT).send().unwrap().error_for_status().unwrap_err().status().unwrap(), 404);
}

#[test]
fn shared_rustls_configuration_is_accepted_without_a_backend_fallback() {
    let _isolation = Isolation::new();
    let server = Server::new(Some("trusted"), false, ok_response());
    let client = reqwest::blocking::Client::builder().no_proxy()
        .tls_backend_preconfigured(hbb_common::verifier::client_config(false).unwrap())
        .build().unwrap();
    assert_eq!(client.get(server.url("https")).timeout(TIMEOUT).send().unwrap().status(), 200);
}

#[test]
fn tls_cache_uses_https_proxy_only_for_plain_destinations() {
    let _isolation = Isolation::new();
    let proxy = Some(Socks5Server { proxy: "https://127.0.0.1:9443".into(), ..Default::default() });
    assert_eq!(http_client::get_url_for_tls("http://127.0.0.1:8080", &proxy), "https://127.0.0.1:9443");
    assert_eq!(http_client::get_url_for_tls("https://127.0.0.1:8443", &proxy), "https://127.0.0.1:8443");
}

#[test]
fn desktop_rustls_preserves_http11_alpn_for_synchronous_clients() {
    let _isolation = Isolation::new();
    let server = Server::new(Some("alpn"), false, ok_response());
    let client = http_client::create_http_client(TlsType::Rustls, false).unwrap();
    assert_eq!(client.get(server.url("https")).timeout(TIMEOUT).send().unwrap().status(), 200);
    assert_eq!(server.requests().len(), 1);
}

#[tokio::test]
async fn desktop_rustls_preserves_http11_alpn_for_asynchronous_clients() {
    let _isolation = Isolation::new();
    let server = Server::new(Some("alpn"), false, ok_response());
    let client = http_client::create_http_client_async(TlsType::Rustls, false).unwrap();
    assert_eq!(client.get(server.url("https")).timeout(TIMEOUT).send().await.unwrap().status(), 200);
    assert_eq!(server.requests().len(), 1);
}
