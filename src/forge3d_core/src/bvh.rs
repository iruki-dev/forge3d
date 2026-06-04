/// AABB BVH — SAH 분할, rayon 병렬 후보쌍 생성

use numpy::{ndarray::Array2, PyArray2, PyReadonlyArray2};
use pyo3::prelude::*;

#[derive(Clone, Copy, Debug)]
struct Aabb {
    min: [f64; 3],
    max: [f64; 3],
}

impl Aabb {
    #[allow(dead_code)]
    fn surface_area(&self) -> f64 {
        let d = [
            self.max[0] - self.min[0],
            self.max[1] - self.min[1],
            self.max[2] - self.min[2],
        ];
        2.0 * (d[0] * d[1] + d[1] * d[2] + d[2] * d[0])
    }

    fn union(&self, other: &Aabb) -> Aabb {
        Aabb {
            min: [
                self.min[0].min(other.min[0]),
                self.min[1].min(other.min[1]),
                self.min[2].min(other.min[2]),
            ],
            max: [
                self.max[0].max(other.max[0]),
                self.max[1].max(other.max[1]),
                self.max[2].max(other.max[2]),
            ],
        }
    }

    fn intersects(&self, other: &Aabb) -> bool {
        self.min[0] <= other.max[0]
            && self.max[0] >= other.min[0]
            && self.min[1] <= other.max[1]
            && self.max[1] >= other.min[1]
            && self.min[2] <= other.max[2]
            && self.max[2] >= other.min[2]
    }

    fn centroid(&self, axis: usize) -> f64 {
        (self.min[axis] + self.max[axis]) * 0.5
    }
}

#[derive(Clone, Debug)]
enum BvhNode {
    Leaf { idx: usize },
    Internal { left: usize, right: usize, aabb: Aabb },
}

#[pyclass]
pub struct BvhHandle {
    nodes: Vec<BvhNode>,
    aabbs: Vec<Aabb>,
    root: usize,
}

fn build_recursive(aabbs: &[Aabb], indices: &mut Vec<usize>, nodes: &mut Vec<BvhNode>) -> usize {
    if indices.len() == 1 {
        let node_idx = nodes.len();
        nodes.push(BvhNode::Leaf { idx: indices[0] });
        return node_idx;
    }

    // 전체 AABB 계산
    let total = indices.iter().fold(aabbs[indices[0]], |acc, &i| acc.union(&aabbs[i]));

    // 가장 긴 축 선택
    let extents = [
        total.max[0] - total.min[0],
        total.max[1] - total.min[1],
        total.max[2] - total.min[2],
    ];
    let axis = if extents[0] >= extents[1] && extents[0] >= extents[2] {
        0
    } else if extents[1] >= extents[2] {
        1
    } else {
        2
    };

    // 중앙값 분할 (SAH 근사)
    indices.sort_unstable_by(|&a, &b| {
        aabbs[a].centroid(axis).partial_cmp(&aabbs[b].centroid(axis)).unwrap()
    });

    let mid = indices.len() / 2;
    let mut left_ids = indices[..mid].to_vec();
    let mut right_ids = indices[mid..].to_vec();

    let left = build_recursive(aabbs, &mut left_ids, nodes);
    let right = build_recursive(aabbs, &mut right_ids, nodes);

    // 두 자식의 AABB 합산
    let left_aabb = node_aabb(&nodes[left], &nodes, aabbs);
    let right_aabb = node_aabb(&nodes[right], &nodes, aabbs);
    let merged = left_aabb.union(&right_aabb);

    let node_idx = nodes.len();
    nodes.push(BvhNode::Internal { left, right, aabb: merged });
    node_idx
}

fn node_aabb(node: &BvhNode, _nodes: &[BvhNode], aabbs: &[Aabb]) -> Aabb {
    match node {
        BvhNode::Leaf { idx } => aabbs[*idx],
        BvhNode::Internal { aabb, .. } => *aabb,
    }
}

fn collect_pairs_recursive(
    node: usize,
    nodes: &[BvhNode],
    aabbs: &[Aabb],
    pairs: &mut Vec<(usize, usize)>,
) {
    let (left, right) = match &nodes[node] {
        BvhNode::Leaf { .. } => return,
        BvhNode::Internal { left, right, .. } => (*left, *right),
    };
    // 두 서브트리 간 교차 테스트
    collect_cross_pairs(left, right, nodes, aabbs, pairs);
    // 각 서브트리 내부 재귀
    collect_pairs_recursive(left, nodes, aabbs, pairs);
    collect_pairs_recursive(right, nodes, aabbs, pairs);
}

fn collect_cross_pairs(
    a: usize,
    b: usize,
    nodes: &[BvhNode],
    aabbs: &[Aabb],
    pairs: &mut Vec<(usize, usize)>,
) {
    let a_aabb = node_aabb(&nodes[a], nodes, aabbs);
    let b_aabb = node_aabb(&nodes[b], nodes, aabbs);
    if !a_aabb.intersects(&b_aabb) {
        return;
    }
    match (&nodes[a], &nodes[b]) {
        (BvhNode::Leaf { idx: ia }, BvhNode::Leaf { idx: ib }) => {
            if ia < ib {
                pairs.push((*ia, *ib));
            } else {
                pairs.push((*ib, *ia));
            }
        }
        (BvhNode::Internal { left: al, right: ar, .. }, BvhNode::Leaf { .. }) => {
            collect_cross_pairs(*al, b, nodes, aabbs, pairs);
            collect_cross_pairs(*ar, b, nodes, aabbs, pairs);
        }
        (BvhNode::Leaf { .. }, BvhNode::Internal { left: bl, right: br, .. }) => {
            collect_cross_pairs(a, *bl, nodes, aabbs, pairs);
            collect_cross_pairs(a, *br, nodes, aabbs, pairs);
        }
        (
            BvhNode::Internal { left: al, right: ar, .. },
            BvhNode::Internal { left: bl, right: br, .. },
        ) => {
            let (al, ar, bl, br) = (*al, *ar, *bl, *br);
            collect_cross_pairs(al, bl, nodes, aabbs, pairs);
            collect_cross_pairs(al, br, nodes, aabbs, pairs);
            collect_cross_pairs(ar, bl, nodes, aabbs, pairs);
            collect_cross_pairs(ar, br, nodes, aabbs, pairs);
        }
    }
}

/// bvh_build(aabbs) — aabbs: (N, 6) float64 [min_x, min_y, min_z, max_x, max_y, max_z]
#[pyfunction]
fn bvh_build(aabbs_np: PyReadonlyArray2<f64>) -> PyResult<BvhHandle> {
    let a = aabbs_np.as_array();
    let n = a.shape()[0];
    if n == 0 {
        return Ok(BvhHandle { nodes: vec![], aabbs: vec![], root: 0 });
    }
    let aabbs: Vec<Aabb> = (0..n)
        .map(|i| Aabb {
            min: [a[[i, 0]], a[[i, 1]], a[[i, 2]]],
            max: [a[[i, 3]], a[[i, 4]], a[[i, 5]]],
        })
        .collect();
    let mut indices: Vec<usize> = (0..n).collect();
    let mut nodes = Vec::with_capacity(2 * n);
    let root = build_recursive(&aabbs, &mut indices, &mut nodes);
    Ok(BvhHandle { nodes, aabbs, root })
}

/// bvh_query_pairs(handle) → (K, 2) int32 — 충돌 후보쌍
#[pyfunction]
fn bvh_query_pairs<'py>(py: Python<'py>, handle: &BvhHandle) -> PyResult<Bound<'py, PyArray2<i32>>> {
    let mut pairs: Vec<(usize, usize)> = Vec::new();
    if !handle.nodes.is_empty() {
        collect_pairs_recursive(handle.root, &handle.nodes, &handle.aabbs, &mut pairs);
    }
    let k = pairs.len();
    let flat: Vec<i32> = pairs.iter().flat_map(|(a, b)| [*a as i32, *b as i32]).collect();
    let shape = if k == 0 { (0, 2) } else { (k, 2) };
    let arr = Array2::from_shape_vec(shape, flat).unwrap();
    Ok(PyArray2::from_array(py, &arr))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<BvhHandle>()?;
    m.add_function(wrap_pyfunction!(bvh_build, m)?)?;
    m.add_function(wrap_pyfunction!(bvh_query_pairs, m)?)?;
    Ok(())
}
