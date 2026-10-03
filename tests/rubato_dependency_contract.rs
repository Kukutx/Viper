//! Exercises the optional production helper without changing the streaming audio backend.
use librustdesk::common::resample_channels;

const FRAMES: usize = 4096;
const RATES: [(u32, u32); 6] = [
    (24_000, 48_000),
    (44_100, 48_000),
    (48_000, 24_000),
    (48_000, 44_100),
    (48_000, 48_000),
    (96_000, 48_000),
];

fn tone(rate: u32, frequency: f32) -> Vec<f32> {
    (0..FRAMES)
        .map(|frame| (std::f32::consts::TAU * frequency * frame as f32 / rate as f32).sin() * 0.25)
        .collect()
}

fn settled_rms(samples: &[f32]) -> f32 {
    let samples = &samples[512..samples.len() - 256];
    (samples.iter().map(|sample| sample * sample).sum::<f32>() / samples.len() as f32).sqrt()
}

#[test]
fn mono_and_stereo_silence_keep_the_fixed_input_frame_contract() {
    for (input_rate, output_rate) in RATES {
        for channels in [1, 2] {
            let input = vec![0.0; FRAMES * usize::from(channels)];
            let output = resample_channels(&input, input_rate, output_rate, channels);
            // Rubato 5's fixed-input sinc keeps two look-ahead frames in the first chunk.
            let expected_frames = ((FRAMES - 2) as f64 * f64::from(output_rate) / f64::from(input_rate)).floor() as usize;
            assert_eq!(output.len(), expected_frames * usize::from(channels));
            assert!(output.iter().all(|sample| *sample == 0.0));
        }
    }
}

#[test]
fn interleaved_stereo_matches_two_independent_mono_channels() {
    for (input_rate, output_rate) in RATES {
        let left = tone(input_rate, 997.0);
        let right = tone(input_rate, 2111.0);
        let interleaved: Vec<_> = left.iter().zip(&right).flat_map(|(a, b)| [*a, *b]).collect();
        let stereo = resample_channels(&interleaved, input_rate, output_rate, 2);
        let mono_left = resample_channels(&left, input_rate, output_rate, 1);
        let mono_right = resample_channels(&right, input_rate, output_rate, 1);
        assert!(!mono_left.is_empty());
        assert_eq!(stereo.len(), mono_left.len() * 2);
        assert_eq!(mono_left.len(), mono_right.len());
        for (frame, (left, right)) in stereo.chunks_exact(2).zip(mono_left.iter().zip(&mono_right)) {
            assert!((frame[0] - left).abs() < 0.000_001);
            assert!((frame[1] - right).abs() < 0.000_001);
        }
    }
}

#[test]
fn sinc_retains_passband_gain_and_rejects_downsampling_aliases() {
    let low = resample_channels(&tone(48_000, 1000.0), 48_000, 24_000, 1);
    let high = resample_channels(&tone(48_000, 18_000.0), 48_000, 24_000, 1);
    assert!(low.iter().chain(&high).all(|sample| sample.is_finite()));
    let expected_rms = 0.25 / 2.0_f32.sqrt();
    assert!((settled_rms(&low) - expected_rms).abs() < 0.002);
    assert!(settled_rms(&high) < 0.000_1);
}

#[test]
fn malformed_input_returns_empty_without_panicking() {
    for (input_rate, output_rate, channels) in [
        (0, 48_000, 1), (48_000, 0, 1), (48_000, 48_000, 0),
        (48_000, 48_000, 3), (48_000, 48_000, u16::MAX),
    ] {
        assert!(resample_channels(&[0.25; 6], input_rate, output_rate, channels).is_empty());
    }
    assert!(resample_channels(&[0.25; 3], 48_000, 24_000, 2).is_empty());
    assert!(resample_channels(&[], 48_000, 24_000, 2).is_empty());
}

#[test]
fn each_call_has_independent_filter_state_and_does_not_mutate_input() {
    let input = tone(44_100, 997.0);
    let original = input.clone();
    let first = resample_channels(&input, 44_100, 48_000, 1);
    let silent = resample_channels(&vec![0.0; FRAMES], 44_100, 48_000, 1);
    let second = resample_channels(&input, 44_100, 48_000, 1);
    assert!(!first.is_empty());
    assert_eq!(first, second);
    assert!(silent.iter().all(|sample| *sample == 0.0));
    assert_eq!(input, original);
}
