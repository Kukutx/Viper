use super::{AudioBuffer, AUDIO_BUFFER_MS};
use ringbuf::{traits::{Consumer, Observer}, HeapRb};
use std::{
    collections::VecDeque,
    sync::{atomic::{AtomicUsize, Ordering}, Arc, Mutex},
};

fn buffer(capacity: usize) -> AudioBuffer {
    AudioBuffer(
        Arc::new(Mutex::new(HeapRb::new(capacity))),
        48_000 * 2,
        [0; 30],
        Arc::new(AtomicUsize::new(0)),
    )
}

fn samples(buffer: &AudioBuffer) -> Vec<f32> {
    buffer.0.lock().unwrap().iter().copied().collect()
}

#[test]
fn overwrite_and_partial_reads_match_fifo_across_wraps() {
    for capacity in [1, 2, 3, 4, 9, 16] {
        let buffer = buffer(capacity);
        let mut expected = VecDeque::<f32>::new();
        let mut generation = 0;
        for step in 0..128 {
            let input: Vec<_> = (0..step % (capacity + 4))
                .map(|offset| (step * 32 + offset) as f32)
                .collect();
            if expected.len() + input.len() > capacity {
                generation += 1;
            }
            expected.extend(&input);
            while expected.len() > capacity {
                expected.pop_front();
            }
            assert_eq!(buffer.append_pcm2(&input), expected.len());
            assert_eq!(buffer.3.load(Ordering::Relaxed), generation);
            assert_eq!(samples(&buffer), expected.iter().copied().collect::<Vec<_>>());
            let mut output = vec![0.0; step % (capacity + 1)];
            let count = buffer.0.lock().unwrap().pop_slice(&mut output);
            let expected_count = expected.len().min(output.len());
            assert_eq!(count, expected_count);
            assert_eq!(output[..count], expected.drain(..expected_count).collect::<Vec<_>>());
            let skip = step % 3;
            let expected_skip = expected.len().min(skip);
            assert_eq!(buffer.0.lock().unwrap().skip(skip), expected_skip);
            expected.drain(..expected_skip);
            assert_eq!(samples(&buffer), expected.iter().copied().collect::<Vec<_>>());
        }
    }
}

#[test]
fn empty_input_preserves_pending_pcm_and_generation() {
    let buffer = buffer(4);
    buffer.append_pcm2(&[1.0, 2.0, 3.0, 4.0, 5.0]);
    assert_eq!(buffer.append_pcm2(&[]), 4);
    assert_eq!(samples(&buffer), [2.0, 3.0, 4.0, 5.0]);
    assert_eq!(buffer.3.load(Ordering::Relaxed), 1);
}

#[test]
fn overwrite_keeps_stereo_order_for_oversized_packets() {
    let buffer = buffer(6);
    buffer.append_pcm2(&[1.0, -1.0, 2.0, -2.0]);
    buffer.append_pcm2(&[3.0, -3.0, 4.0, -4.0]);
    assert_eq!(samples(&buffer), [2.0, -2.0, 3.0, -3.0, 4.0, -4.0]);
    buffer.append_pcm2(&[5.0, -5.0, 6.0, -6.0, 7.0, -7.0, 8.0, -8.0]);
    assert_eq!(samples(&buffer), [6.0, -6.0, 7.0, -7.0, 8.0, -8.0]);
    assert_eq!(buffer.3.load(Ordering::Relaxed), 2);
}

#[test]
fn unchanged_capacity_preserves_pending_pcm_and_shared_handles() {
    let mut buffer = AudioBuffer::default();
    buffer.append_pcm2(&[0.1, -0.1]);
    let shared = buffer.0.clone();
    let generation = buffer.3.clone();
    buffer.resize(48_000, 2);
    assert!(Arc::ptr_eq(&shared, &buffer.0));
    assert!(Arc::ptr_eq(&generation, &buffer.3));
    assert_eq!(samples(&buffer), [0.1, -0.1]);
    assert_eq!(buffer.0.lock().unwrap().capacity().get(), 48_000 * 2 * AUDIO_BUFFER_MS / 1000);
}

#[test]
fn changed_capacity_clears_pcm_without_replacing_shared_handles() {
    let mut buffer = AudioBuffer::default();
    buffer.append_pcm2(&[0.1, -0.1]);
    let shared = buffer.0.clone();
    let generation = buffer.3.clone();
    buffer.resize(24_000, 1);
    assert!(Arc::ptr_eq(&shared, &buffer.0));
    assert!(Arc::ptr_eq(&generation, &buffer.3));
    assert!(samples(&buffer).is_empty());
    assert_eq!(buffer.0.lock().unwrap().capacity().get(), 24_000 * AUDIO_BUFFER_MS / 1000);
    assert_eq!(buffer.1, 24_000);
}

#[test]
fn overflow_generation_wraps_without_changing_sample_order() {
    let buffer = buffer(2);
    buffer.3.store(usize::MAX, Ordering::Relaxed);
    buffer.append_pcm2(&[1.0, 2.0]);
    assert_eq!(buffer.3.load(Ordering::Relaxed), usize::MAX);
    buffer.append_pcm2(&[3.0]);
    assert_eq!(buffer.3.load(Ordering::Relaxed), 0);
    assert_eq!(samples(&buffer), [2.0, 3.0]);
}

#[test]
fn repeated_producer_overwrite_reuses_allocated_storage() {
    let buffer = buffer(8);
    let input = [0.25; 12];
    buffer.append_pcm2(&input);
    crate::audio_resampler::allocation_tests::assert_no_allocations(|| {
        for _ in 0..100 {
            assert_eq!(buffer.append_pcm2(&input), 8);
        }
    });
    assert_eq!(samples(&buffer), [0.25; 8]);
    assert_eq!(buffer.3.load(Ordering::Relaxed), 101);
}
