/// GJK 충돌 감지 + EPA 관입 깊이/법선 계산

use glam::DVec3;
use numpy::{ndarray::ArrayView2, PyArray1, PyReadonlyArray2};
use pyo3::prelude::*;

// ────────────────────────── Support function ──────────────────────────

fn support(verts: &ArrayView2<f64>, dir: DVec3) -> DVec3 {
    let n = verts.shape()[0];
    let mut best = f64::NEG_INFINITY;
    let mut best_v = DVec3::ZERO;
    for i in 0..n {
        let v = DVec3::new(verts[[i, 0]], verts[[i, 1]], verts[[i, 2]]);
        let d = v.dot(dir);
        if d > best {
            best = d;
            best_v = v;
        }
    }
    best_v
}

fn minkowski_support(a: &ArrayView2<f64>, b: &ArrayView2<f64>, dir: DVec3) -> DVec3 {
    support(a, dir) - support(b, -dir)
}

// ────────────────────────── GJK ──────────────────────────

struct Simplex {
    pts: Vec<DVec3>,
}

impl Simplex {
    fn new() -> Self { Simplex { pts: Vec::with_capacity(4) } }
    fn push(&mut self, p: DVec3) { self.pts.insert(0, p); }
    fn len(&self) -> usize { self.pts.len() }
}

fn triple(a: DVec3, b: DVec3, c: DVec3) -> DVec3 {
    a.cross(b).cross(c)
}

fn nearest_simplex(simplex: &mut Simplex) -> DVec3 {
    match simplex.len() {
        2 => line_case(simplex),
        3 => triangle_case(simplex),
        4 => tetrahedron_case(simplex),
        _ => unreachable!(),
    }
}

fn line_case(s: &mut Simplex) -> DVec3 {
    let (b, a) = (s.pts[1], s.pts[0]);
    let ab = b - a;
    let ao = -a;
    if ab.dot(ao) > 0.0 {
        triple(ab, ao, ab)
    } else {
        s.pts = vec![a];
        ao
    }
}

fn triangle_case(s: &mut Simplex) -> DVec3 {
    let (c, b, a) = (s.pts[2], s.pts[1], s.pts[0]);
    let ab = b - a;
    let ac = c - a;
    let ao = -a;
    let abc = ab.cross(ac);

    if triple(abc, ac, ac).dot(ao) > 0.0 {
        if ac.dot(ao) > 0.0 {
            s.pts = vec![a, c];
            triple(ac, ao, ac)
        } else {
            s.pts = vec![a, b];
            line_case(s)
        }
    } else if triple(ab, abc, ab).dot(ao) > 0.0 {
        s.pts = vec![a, b];
        line_case(s)
    } else if abc.dot(ao) > 0.0 {
        abc
    } else {
        s.pts = vec![a, b, c]; // reorder
        -abc
    }
}

fn tetrahedron_case(s: &mut Simplex) -> DVec3 {
    let (d, c, b, a) = (s.pts[3], s.pts[2], s.pts[1], s.pts[0]);
    let ab = b - a;
    let ac = c - a;
    let ad = d - a;
    let ao = -a;

    let abc = ab.cross(ac);
    let acd = ac.cross(ad);
    let adb = ad.cross(ab);

    if abc.dot(ao) > 0.0 {
        s.pts = vec![a, b, c];
        triangle_case(s)
    } else if acd.dot(ao) > 0.0 {
        s.pts = vec![a, c, d];
        triangle_case(s)
    } else if adb.dot(ao) > 0.0 {
        s.pts = vec![a, d, b];
        triangle_case(s)
    } else {
        DVec3::ZERO // 원점이 테트라헤드론 내부 → 충돌
    }
}

fn gjk(a: &ArrayView2<f64>, b: &ArrayView2<f64>) -> (bool, Simplex) {
    let mut dir = DVec3::X;
    let mut simplex = Simplex::new();
    simplex.push(minkowski_support(a, b, dir));
    dir = -simplex.pts[0];

    for _ in 0..64 {
        let pt = minkowski_support(a, b, dir);
        if pt.dot(dir) < 0.0 {
            return (false, simplex);
        }
        simplex.push(pt);
        let new_dir = nearest_simplex(&mut simplex);
        if new_dir.length_squared() < 1e-14 {
            return (true, simplex);
        }
        dir = new_dir;
    }
    (false, simplex)
}

// ────────────────────────── EPA ──────────────────────────

#[derive(Clone)]
struct Face {
    verts: [DVec3; 3],
    normal: DVec3,
    dist: f64,
}

fn make_face(a: DVec3, b: DVec3, c: DVec3) -> Face {
    let n = (b - a).cross(c - a);
    let len = n.length();
    let normal = if len > 1e-15 { n / len } else { DVec3::Y };
    let dist = normal.dot(a);
    Face { verts: [a, b, c], normal, dist }
}

fn epa(a_verts: &ArrayView2<f64>, b_verts: &ArrayView2<f64>, simplex: Simplex) -> (DVec3, f64) {
    // 테트라헤드론 초기화
    let pts = &simplex.pts;
    if pts.len() < 4 {
        // 퇴화 심플렉스: 작은 관입 반환
        return (DVec3::Y, 0.0);
    }
    let (a, b, c, d) = (pts[0], pts[1], pts[2], pts[3]);
    let mut polytope: Vec<Face> = vec![
        make_face(a, b, c),
        make_face(a, c, d),
        make_face(a, d, b),
        make_face(b, d, c),
    ];

    for _ in 0..64 {
        // 원점에 가장 가까운 면 선택
        let (_min_idx, min_face) = polytope
            .iter()
            .enumerate()
            .min_by(|(_, f1), (_, f2)| f1.dist.partial_cmp(&f2.dist).unwrap())
            .map(|(i, f)| (i, f.clone()))
            .unwrap();

        let support_pt = minkowski_support(a_verts, b_verts, min_face.normal);
        let new_dist = support_pt.dot(min_face.normal);

        if (new_dist - min_face.dist).abs() < 1e-9 {
            return (min_face.normal, min_face.dist);
        }

        // 지평선 에지 수집
        let mut edges: Vec<(DVec3, DVec3)> = Vec::new();
        let mut to_remove: Vec<usize> = Vec::new();

        for (i, face) in polytope.iter().enumerate() {
            if face.normal.dot(support_pt - face.verts[0]) > 0.0 {
                to_remove.push(i);
                for &(vi, vj) in &[(0, 1), (1, 2), (2, 0)] {
                    let e = (face.verts[vi], face.verts[vj]);
                    if let Some(pos) = edges.iter().position(|&(a, b)| a == e.1 && b == e.0) {
                        edges.swap_remove(pos);
                    } else {
                        edges.push(e);
                    }
                }
            }
        }

        for &i in to_remove.iter().rev() {
            polytope.swap_remove(i);
        }
        for (ea, eb) in edges {
            polytope.push(make_face(support_pt, ea, eb));
        }
    }
    (DVec3::Y, 0.0)
}

// ────────────────────────── Public API ──────────────────────────

/// gjk_query(verts_a, verts_b) → (colliding: bool, normal: (3,), depth: float)
#[pyfunction]
fn gjk_query<'py>(
    py: Python<'py>,
    verts_a: PyReadonlyArray2<'py, f64>,
    verts_b: PyReadonlyArray2<'py, f64>,
) -> PyResult<(bool, Bound<'py, PyArray1<f64>>, f64)> {
    let a = verts_a.as_array();
    let b = verts_b.as_array();

    let (colliding, simplex) = gjk(&a, &b);

    if !colliding {
        let normal = PyArray1::from_vec(py, vec![0.0, 0.0, 0.0]);
        return Ok((false, normal, 0.0));
    }

    let (normal_vec, depth) = epa(&a, &b, simplex);
    let normal = PyArray1::from_vec(py, vec![normal_vec.x, normal_vec.y, normal_vec.z]);
    Ok((true, normal, depth))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(gjk_query, m)?)?;
    Ok(())
}
