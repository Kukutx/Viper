use hbb_common::{
    async_recursion::async_recursion,
    bail,
    config::{Config, Socks5Server},
    log,
    proxy::{Proxy, ProxyScheme},
    tls::{
        get_cached_tls_accept_invalid_cert, get_cached_tls_type, is_plain, upsert_tls_cache,
        TlsType,
    },
    ResultType,
};
use reqwest::{blocking::Client as SyncClient, Client as AsyncClient};

#[derive(Debug)]
pub enum HttpClientConfigError {
    Proxy,
    Tls,
    Builder,
}

impl std::fmt::Display for HttpClientConfigError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            Self::Proxy => "Invalid configured HTTP proxy",
            Self::Tls => "Failed to initialize configured HTTP TLS backend",
            Self::Builder => "Failed to build configured HTTP client",
        })
    }
}

impl std::error::Error for HttpClientConfigError {}

macro_rules! configure_http_client {
    ($builder:expr, $tls_type:expr, $danger_accept_invalid_cert:expr, $Client:ty) => {{
        (|| -> ResultType<$Client> {
            // Explicit proxy configuration must never fall back to ambient proxies or direct I/O.
            let mut builder = $builder.no_proxy();
            match $tls_type {
                TlsType::Plain => {}
                TlsType::NativeTls => {
                    builder = builder.tls_backend_native();
                    if $danger_accept_invalid_cert {
                        builder = builder.tls_danger_accept_invalid_certs(true);
                    }
                }
                TlsType::Rustls => {
                    let client_config = hbb_common::verifier::client_config($danger_accept_invalid_cert)
                        .map_err(|_| HttpClientConfigError::Tls)?;
                    #[cfg(not(any(target_os = "android", target_os = "ios")))]
                    let client_config = {
                        let mut config = client_config;
                        config.alpn_protocols = vec![b"http/1.1".to_vec()];
                        config
                    };
                    builder = builder.tls_backend_preconfigured(client_config);
                }
            }
            if let Some(conf) = Config::get_socks() {
                // Parser errors can contain proxy userinfo. Do not expose it to logs or the UI.
                let proxy = Proxy::from_conf(&conf, None)
                    .map_err(|_| HttpClientConfigError::Proxy)?;
                let proxy_setup = match &proxy.intercept {
                    ProxyScheme::Http { host, .. } => reqwest::Proxy::all(format!("http://{}", host)),
                    ProxyScheme::Https { host, .. } => reqwest::Proxy::all(format!("https://{}", host)),
                    ProxyScheme::Socks5 { addr, .. } => reqwest::Proxy::all(format!("socks5://{}", addr)),
                };
                let mut configured = proxy_setup
                    .map_err(|_| HttpClientConfigError::Proxy)?;
                if let Some(auth) = proxy.intercept.maybe_auth() {
                    if !auth.username().is_empty() && !auth.password().is_empty() {
                        configured = configured.basic_auth(auth.username(), auth.password());
                    }
                }
                builder = builder.proxy(configured);
            }
            Ok(builder.build().map_err(|_| HttpClientConfigError::Builder)?)
        })()
    }};
}

pub fn create_http_client(
    tls_type: TlsType,
    danger_accept_invalid_cert: bool,
) -> ResultType<SyncClient> {
    let builder = SyncClient::builder();
    configure_http_client!(builder, tls_type, danger_accept_invalid_cert, SyncClient)
}

pub fn create_http_client_async(
    tls_type: TlsType,
    danger_accept_invalid_cert: bool,
) -> ResultType<AsyncClient> {
    let builder = AsyncClient::builder();
    configure_http_client!(builder, tls_type, danger_accept_invalid_cert, AsyncClient)
}

pub fn get_url_for_tls<'a>(url: &'a str, proxy_conf: &'a Option<Socks5Server>) -> &'a str {
    if is_plain(url) {
        if let Some(conf) = proxy_conf {
            if conf.proxy.starts_with("https://") {
                return &conf.proxy;
            }
        }
    }
    url
}

pub fn create_http_client_with_url(url: &str) -> ResultType<SyncClient> {
    let proxy_conf = Config::get_socks();
    let tls_url = get_url_for_tls(url, &proxy_conf);
    let tls_type = get_cached_tls_type(tls_url);
    let is_tls_type_cached = tls_type.is_some();
    let tls_type = tls_type.unwrap_or(TlsType::Rustls);
    let tls_danger_accept_invalid_cert = get_cached_tls_accept_invalid_cert(tls_url);
    create_http_client_with_url_(
        url,
        tls_url,
        tls_type,
        is_tls_type_cached,
        tls_danger_accept_invalid_cert,
        tls_danger_accept_invalid_cert,
        false,
    )
}

pub fn create_http_client_with_url_strict(url: &str) -> ResultType<SyncClient> {
    let parsed_url = url::Url::parse(url)?;
    if parsed_url.scheme() != "https" {
        bail!("Strict HTTP client requires HTTPS: {}", url);
    }
    let proxy_conf = Config::get_socks();
    let tls_url = get_url_for_tls(url, &proxy_conf);
    let cached_tls_type = get_cached_tls_type(tls_url);
    let cached_danger_accept_invalid_cert = get_cached_tls_accept_invalid_cert(tls_url);
    let can_reuse_cached_probe =
        matches!(cached_tls_type, Some(TlsType::Rustls | TlsType::NativeTls))
            && cached_danger_accept_invalid_cert == Some(false);
    let tls_type = if can_reuse_cached_probe {
        cached_tls_type.unwrap_or(TlsType::Rustls)
    } else {
        TlsType::Rustls
    };
    create_http_client_with_url_(
        url,
        tls_url,
        tls_type,
        can_reuse_cached_probe,
        Some(false),
        Some(false),
        true,
    )
}

fn create_http_client_with_url_(
    url: &str,
    tls_url: &str,
    tls_type: TlsType,
    is_tls_type_cached: bool,
    danger_accept_invalid_cert: Option<bool>,
    original_danger_accept_invalid_cert: Option<bool>,
    https_only: bool,
) -> ResultType<SyncClient> {
    let builder = SyncClient::builder().https_only(https_only);
    let mut client = configure_http_client!(
        builder, tls_type, danger_accept_invalid_cert.unwrap_or(false), SyncClient
    )?;
    if is_tls_type_cached && original_danger_accept_invalid_cert.is_some() {
        return Ok(client);
    }
    if let Err(e) = client.head(url).send() {
        if e.is_request() {
            match (tls_type, is_tls_type_cached, danger_accept_invalid_cert) {
                (TlsType::Rustls, _, None) => {
                    log::warn!(
                        "Failed to connect to server {} with rustls-tls: {:?}, trying accept invalid cert",
                        tls_url,
                        e
                    );
                    client = create_http_client_with_url_(
                        url,
                        tls_url,
                        tls_type,
                        is_tls_type_cached,
                        Some(true),
                        original_danger_accept_invalid_cert,
                        https_only,
                    )?;
                }
                (TlsType::Rustls, false, Some(_)) => {
                    log::warn!(
                        "Failed to connect to server {} with rustls-tls: {:?}, trying native-tls",
                        tls_url,
                        e
                    );
                    client = create_http_client_with_url_(
                        url,
                        tls_url,
                        TlsType::NativeTls,
                        is_tls_type_cached,
                        original_danger_accept_invalid_cert,
                        original_danger_accept_invalid_cert,
                        https_only,
                    )?;
                }
                (TlsType::NativeTls, _, None) => {
                    log::warn!(
                        "Failed to connect to server {} with native-tls: {:?}, trying accept invalid cert",
                        tls_url,
                        e
                    );
                    client = create_http_client_with_url_(
                        url,
                        tls_url,
                        tls_type,
                        is_tls_type_cached,
                        Some(true),
                        original_danger_accept_invalid_cert,
                        https_only,
                    )?;
                }
                _ => {
                    log::error!(
                        "Failed to connect to server {} with {:?}, err: {:?}.",
                        tls_url,
                        tls_type,
                        e
                    );
                }
            }
        } else {
            log::warn!(
                "Failed to connect to server {} with {:?}, err: {}.",
                tls_url,
                tls_type,
                e
            );
        }
    } else {
        log::info!(
            "Successfully connected to server {} with {:?}",
            tls_url,
            tls_type
        );
        upsert_tls_cache(
            tls_url,
            tls_type,
            danger_accept_invalid_cert.unwrap_or(false),
        );
    }
    Ok(client)
}

pub async fn create_http_client_async_with_url(url: &str) -> ResultType<AsyncClient> {
    let proxy_conf = Config::get_socks();
    let tls_url = get_url_for_tls(url, &proxy_conf);
    let tls_type = get_cached_tls_type(tls_url);
    let is_tls_type_cached = tls_type.is_some();
    let tls_type = tls_type.unwrap_or(TlsType::Rustls);
    let danger_accept_invalid_cert = get_cached_tls_accept_invalid_cert(tls_url);
    create_http_client_async_with_url_(
        url,
        tls_url,
        tls_type,
        is_tls_type_cached,
        danger_accept_invalid_cert,
        danger_accept_invalid_cert,
        false,
    )
    .await
}

pub async fn create_http_client_async_with_url_strict(url: &str) -> ResultType<AsyncClient> {
    let parsed_url = url::Url::parse(url)?;
    if parsed_url.scheme() != "https" {
        bail!("Strict HTTP client requires HTTPS: {}", url);
    }
    let proxy_conf = Config::get_socks();
    let tls_url = get_url_for_tls(url, &proxy_conf);
    let cached_tls_type = get_cached_tls_type(tls_url);
    let cached_danger_accept_invalid_cert = get_cached_tls_accept_invalid_cert(tls_url);
    let can_reuse_cached_probe =
        matches!(cached_tls_type, Some(TlsType::Rustls | TlsType::NativeTls))
            && cached_danger_accept_invalid_cert == Some(false);
    let tls_type = if can_reuse_cached_probe {
        cached_tls_type.unwrap_or(TlsType::Rustls)
    } else {
        TlsType::Rustls
    };
    create_http_client_async_with_url_(
        url,
        tls_url,
        tls_type,
        can_reuse_cached_probe,
        Some(false),
        Some(false),
        true,
    )
    .await
}

#[async_recursion]
async fn create_http_client_async_with_url_(
    url: &str,
    tls_url: &str,
    tls_type: TlsType,
    is_tls_type_cached: bool,
    danger_accept_invalid_cert: Option<bool>,
    original_danger_accept_invalid_cert: Option<bool>,
    https_only: bool,
) -> ResultType<AsyncClient> {
    let builder = AsyncClient::builder().https_only(https_only);
    let mut client = configure_http_client!(
        builder, tls_type, danger_accept_invalid_cert.unwrap_or(false), AsyncClient
    )?;
    if is_tls_type_cached && original_danger_accept_invalid_cert.is_some() {
        return Ok(client);
    }
    if let Err(e) = client.head(url).send().await {
        match (tls_type, is_tls_type_cached, danger_accept_invalid_cert) {
            (TlsType::Rustls, _, None) => {
                log::warn!(
                    "Failed to connect to server {} with rustls-tls: {:?}, trying accept invalid cert",
                    tls_url,
                    e
                );
                client = create_http_client_async_with_url_(
                    url,
                    tls_url,
                    tls_type,
                    is_tls_type_cached,
                    Some(true),
                    original_danger_accept_invalid_cert,
                    https_only,
                )
                .await?;
            }
            (TlsType::Rustls, false, Some(_)) => {
                log::warn!(
                    "Failed to connect to server {} with rustls-tls: {:?}, trying native-tls",
                    tls_url,
                    e
                );
                client = create_http_client_async_with_url_(
                    url,
                    tls_url,
                    TlsType::NativeTls,
                    is_tls_type_cached,
                    original_danger_accept_invalid_cert,
                    original_danger_accept_invalid_cert,
                    https_only,
                )
                .await?;
            }
            (TlsType::NativeTls, _, None) => {
                log::warn!(
                    "Failed to connect to server {} with native-tls: {:?}, trying accept invalid cert",
                    tls_url,
                    e
                );
                client = create_http_client_async_with_url_(
                    url,
                    tls_url,
                    tls_type,
                    is_tls_type_cached,
                    Some(true),
                    original_danger_accept_invalid_cert,
                    https_only,
                )
                .await?;
            }
            _ => {
                log::error!(
                    "Failed to connect to server {} with {:?}, err: {:?}.",
                    tls_url,
                    tls_type,
                    e
                );
            }
        }
    } else {
        log::info!(
            "Successfully connected to server {} with {:?}",
            tls_url,
            tls_type
        );
        upsert_tls_cache(
            tls_url,
            tls_type,
            danger_accept_invalid_cert.unwrap_or(false),
        );
    }
    Ok(client)
}
