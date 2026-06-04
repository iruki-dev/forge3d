use glam::{DMat4, DQuat, DVec3};
use numpy::{ndarray::ArrayView1, PyArray1, PyArray2, PyReadonlyArray1, PyReadonlyArray2};
use pyo3::prelude::*;

fn arr1_to_dvec3(a: &ArrayView1<f64>) -> DVec3 {
    DVec3::new(a[0], a[1], a[2])
}

fn arr1_to_quat(a: &ArrayView1<f64>) -> DQuat {
    // [w, x, y, z]
    DQuat::from_xyzw(a[1], a[2], a[3], a[0])
}

fn mat4_from_arr(a: &numpy::ndarray::ArrayView2<f64>) -> DMat4 {
    DMat4::from_cols_array(&[
        a[[0, 0]], a[[1, 0]], a[[2, 0]], a[[3, 0]],
        a[[0, 1]], a[[1, 1]], a[[2, 1]], a[[3, 1]],
        a[[0, 2]], a[[1, 2]], a[[2, 2]], a[[3, 2]],
        a[[0, 3]], a[[1, 3]], a[[2, 3]], a[[3, 3]],
    ])
}

fn mat4_to_vec(m: DMat4) -> Vec<f64> {
    let a = m.to_cols_array();
    // col-major → row-major (4×4)
    let mut out = vec![0.0f64; 16];
    for col in 0..4 {
        for row in 0..4 {
            out[row * 4 + col] = a[col * 4 + row];
        }
    }
    out
}

/// se3_mul(a, b) — (4,4) @ (4,4) float64
#[pyfunction]
fn se3_mul<'py>(
    py: Python<'py>,
    a: PyReadonlyArray2<'py, f64>,
    b: PyReadonlyArray2<'py, f64>,
) -> PyResult<Bound<'py, PyArray2<f64>>> {
    let ma = mat4_from_arr(&a.as_array());
    let mb = mat4_from_arr(&b.as_array());
    let mc = ma * mb;
    let flat = mat4_to_vec(mc);
    let arr = numpy::ndarray::Array2::from_shape_vec((4, 4), flat).unwrap();
    Ok(PyArray2::from_array(py, &arr))
}

/// quat_normalize(q) — [w,x,y,z] float64
#[pyfunction]
fn quat_normalize<'py>(
    py: Python<'py>,
    q: PyReadonlyArray1<'py, f64>,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let qq = arr1_to_quat(&q.as_array());
    let qn = qq.normalize();
    let out = vec![qn.w, qn.x, qn.y, qn.z];
    Ok(PyArray1::from_vec(py, out))
}

/// quat_mul(a, b) — [w,x,y,z] × [w,x,y,z]
#[pyfunction]
fn quat_mul<'py>(
    py: Python<'py>,
    a: PyReadonlyArray1<'py, f64>,
    b: PyReadonlyArray1<'py, f64>,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let qa = arr1_to_quat(&a.as_array());
    let qb = arr1_to_quat(&b.as_array());
    let qc = qa * qb;
    Ok(PyArray1::from_vec(py, vec![qc.w, qc.x, qc.y, qc.z]))
}

/// quat_rotate_vec(q, v) — rotate (3,) vector by quaternion [w,x,y,z]
#[pyfunction]
fn quat_rotate_vec<'py>(
    py: Python<'py>,
    q: PyReadonlyArray1<'py, f64>,
    v: PyReadonlyArray1<'py, f64>,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let qq = arr1_to_quat(&q.as_array());
    let vv = arr1_to_dvec3(&v.as_array());
    let rv = qq * vv;
    Ok(PyArray1::from_vec(py, vec![rv.x, rv.y, rv.z]))
}

/// se3_inverse(m) — SE3 matrix inverse (4,4)
#[pyfunction]
fn se3_inverse<'py>(
    py: Python<'py>,
    m: PyReadonlyArray2<'py, f64>,
) -> PyResult<Bound<'py, PyArray2<f64>>> {
    let mm = mat4_from_arr(&m.as_array());
    let inv = mm.inverse();
    let flat = mat4_to_vec(inv);
    let arr = numpy::ndarray::Array2::from_shape_vec((4, 4), flat).unwrap();
    Ok(PyArray2::from_array(py, &arr))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(se3_mul, m)?)?;
    m.add_function(wrap_pyfunction!(quat_normalize, m)?)?;
    m.add_function(wrap_pyfunction!(quat_mul, m)?)?;
    m.add_function(wrap_pyfunction!(quat_rotate_vec, m)?)?;
    m.add_function(wrap_pyfunction!(se3_inverse, m)?)?;
    Ok(())
}
