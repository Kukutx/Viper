//! Public dependency contracts; these tests never extract or launch the application.
#![cfg(windows)]

use std::{io::Read, path::PathBuf};

#[test]
fn brotli_reads_the_pinned_python_producers_binary_stream() {
    // Python Brotli 1.2.0, quality=5, on (b"Viper portable payload\0\xff" * 40).
    let encoded: &[u8] = &[
        27, 191, 3, 0, 68, 79, 38, 197, 215, 164, 223, 8, 54, 27, 211, 132,
        158, 20, 45, 5, 86, 149, 162, 57, 177, 216, 11, 46, 214, 42, 48,
        188, 106, 186, 188, 1,
    ];
    let expected = b"Viper portable payload\0\xff".repeat(40);
    for buffer_size in [1, 4096] {
        let mut decoded = Vec::new();
        brotli::Decompressor::new(encoded, buffer_size)
            .read_to_end(&mut decoded)
            .expect("complete valid stream decoding");
        assert_eq!(decoded, expected);
    }
}

#[test]
fn md5_keeps_the_legacy_payload_field_not_a_security_signature() {
    for (input, expected) in [
        ("", "d41d8cd98f00b204e9800998ecf8427e"),
        ("abc", "900150983cd24fb0d6963f7d28e17f72"),
        ("abcdefghijklmnopqrstuvwxyz", "c3fcd3d76192e4007dfb496cca67e13b"),
    ] {
        assert_eq!(format!("{:x}", md5::compute(input.as_bytes())), expected);
        let mut context = md5::Context::new();
        for chunk in input.as_bytes().chunks(2) {
            context.consume(chunk);
        }
        assert_eq!(format!("{:x}", context.finalize()), expected);
    }
}

#[test]
fn local_data_directory_matches_the_native_runner_profile_without_creating_it() {
    // Opt-in native CI uses the runner's unmodified current-user profile. No
    // data directory, settings file, or application process is created here.
    let expected = PathBuf::from(std::env::var_os("LOCALAPPDATA").expect("native profile fixture"));
    let actual = dirs::data_local_dir().expect("Windows local application data directory");
    assert!(actual.is_absolute());
    assert_eq!(actual.canonicalize().unwrap(), expected.canonicalize().unwrap());
    assert_eq!(dirs::data_local_dir().unwrap(), actual);
}
