mod math_simd;
mod bvh;
mod gjk_epa;
mod pgs_solver;

use pyo3::prelude::*;

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    math_simd::register(m)?;
    bvh::register(m)?;
    gjk_epa::register(m)?;
    pgs_solver::register(m)?;
    Ok(())
}
