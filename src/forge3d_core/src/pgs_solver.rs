/// PGS(Sequential Impulse) 접촉 솔버 — Erin Catto 방식
/// contacts: (C, 10) [pos(3), normal(3), penetration, friction_mu, inv_mass_a, inv_mass_b]
/// velocities: (N, 6) [vx,vy,vz, wx,wy,wz]
/// Returns: (N, 6) 갱신된 속도

use numpy::{ndarray::Array2, PyArray2, PyReadonlyArray2, PyReadonlyArray1};
use pyo3::prelude::*;

#[inline]
fn dot3(a: &[f64], b: &[f64]) -> f64 {
    a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
}

#[inline]
fn cross3(a: &[f64], b: &[f64]) -> [f64; 3] {
    [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ]
}

#[pyfunction]
#[pyo3(signature = (contacts, body_indices, velocities, masses, dt, iterations=10))]
pub fn pgs_solve<'py>(
    py: Python<'py>,
    contacts: PyReadonlyArray2<'py, f64>,
    body_indices: PyReadonlyArray2<'py, i32>,
    velocities: PyReadonlyArray2<'py, f64>,
    masses: PyReadonlyArray1<'py, f64>,
    dt: f64,
    iterations: usize,
) -> PyResult<Bound<'py, PyArray2<f64>>> {
    let c = contacts.as_array();
    let bi = body_indices.as_array();
    let vel = velocities.as_array();
    let mass = masses.as_array();

    let n_contacts = c.shape()[0];
    let n_bodies = vel.shape()[0];

    // 속도 복사 (가변 상태)
    let mut v: Vec<[f64; 6]> = (0..n_bodies)
        .map(|i| [vel[[i,0]], vel[[i,1]], vel[[i,2]], vel[[i,3]], vel[[i,4]], vel[[i,5]]])
        .collect();

    // 누적 임펄스 (Warm starting 없음 — 0 초기화)
    let mut lambda_n: Vec<f64> = vec![0.0; n_contacts];
    let mut lambda_t1: Vec<f64> = vec![0.0; n_contacts];
    let mut lambda_t2: Vec<f64> = vec![0.0; n_contacts];

    let beta = 0.3_f64;
    let slop = 0.001_f64;

    for _ in 0..iterations {
        for ci in 0..n_contacts {
            let norm = [c[[ci,3]], c[[ci,4]], c[[ci,5]]];
            let pen  = c[[ci,6]];
            let mu   = c[[ci,7]];
            let ia   = bi[[ci,0]] as usize;
            let ib   = bi[[ci,1]] as usize;

            let inv_ma = 1.0 / mass[ia].max(1e-9);
            let inv_mb = if ib < n_bodies { 1.0 / mass[ib].max(1e-9) } else { 0.0 };

            // ── 법선 임펄스 ──
            let va = [v[ia][0], v[ia][1], v[ia][2]];
            let vb = if ib < n_bodies { [v[ib][0], v[ib][1], v[ib][2]] } else { [0.0; 3] };
            let rel_vn = dot3(&norm, &[va[0]-vb[0], va[1]-vb[1], va[2]-vb[2]]);

            let bias = beta / dt * (pen - slop).max(0.0);
            let eff_mass = inv_ma + inv_mb;
            let dλ = if eff_mass > 1e-12 { -(rel_vn - bias) / eff_mass } else { 0.0 };

            let old = lambda_n[ci];
            lambda_n[ci] = (old + dλ).max(0.0);
            let actual_dλ = lambda_n[ci] - old;

            // 법선 속도 적용
            for k in 0..3 {
                v[ia][k] += inv_ma * actual_dλ * norm[k];
                if ib < n_bodies {
                    v[ib][k] -= inv_mb * actual_dλ * norm[k];
                }
            }

            // ── 접선 임펄스 (마찰) ──
            // t1 = 임의의 접선 방향
            let t1 = {
                let perp = if norm[0].abs() < 0.9 { [1.0, 0.0, 0.0] } else { [0.0, 1.0, 0.0] };
                let c = cross3(&norm, &perp);
                let len = (c[0]*c[0] + c[1]*c[1] + c[2]*c[2]).sqrt();
                if len > 1e-12 { [c[0]/len, c[1]/len, c[2]/len] } else { [1.0, 0.0, 0.0] }
            };
            let t2 = cross3(&norm, &t1);

            let va = [v[ia][0], v[ia][1], v[ia][2]];
            let vb = if ib < n_bodies { [v[ib][0], v[ib][1], v[ib][2]] } else { [0.0; 3] };
            let rel = [va[0]-vb[0], va[1]-vb[1], va[2]-vb[2]];

            let max_friction = mu * lambda_n[ci];

            // t1
            let rel_vt1 = dot3(&t1, &rel);
            let dλt1 = if eff_mass > 1e-12 { -rel_vt1 / eff_mass } else { 0.0 };
            let old_t1 = lambda_t1[ci];
            lambda_t1[ci] = (old_t1 + dλt1).clamp(-max_friction, max_friction);
            let actual_t1 = lambda_t1[ci] - old_t1;
            for k in 0..3 {
                v[ia][k] += inv_ma * actual_t1 * t1[k];
                if ib < n_bodies { v[ib][k] -= inv_mb * actual_t1 * t1[k]; }
            }

            // t2
            let va = [v[ia][0], v[ia][1], v[ia][2]];
            let vb = if ib < n_bodies { [v[ib][0], v[ib][1], v[ib][2]] } else { [0.0; 3] };
            let rel = [va[0]-vb[0], va[1]-vb[1], va[2]-vb[2]];
            let rel_vt2 = dot3(&t2, &rel);
            let dλt2 = if eff_mass > 1e-12 { -rel_vt2 / eff_mass } else { 0.0 };
            let old_t2 = lambda_t2[ci];
            lambda_t2[ci] = (old_t2 + dλt2).clamp(-max_friction, max_friction);
            let actual_t2 = lambda_t2[ci] - old_t2;
            for k in 0..3 {
                v[ia][k] += inv_ma * actual_t2 * t2[k];
                if ib < n_bodies { v[ib][k] -= inv_mb * actual_t2 * t2[k]; }
            }
        }
    }

    // 결과 배열 구성
    let flat: Vec<f64> = v.iter().flat_map(|row| row.iter().copied()).collect();
    let arr = Array2::from_shape_vec((n_bodies, 6), flat).unwrap();
    Ok(PyArray2::from_array(py, &arr))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(pgs_solve, m)?)?;
    Ok(())
}
