use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn bench_placeholder(c: &mut Criterion) {
    // BVH, GJK, PGS 벤치마크는 Python 경유 없이 Rust 내부 직접 호출로 추가 예정
    c.bench_function("placeholder", |b| b.iter(|| black_box(1 + 1)));
}

criterion_group!(benches, bench_placeholder);
criterion_main!(benches);
