"""05 — ECS 씬: 컴포넌트 조합으로 물리 씬 구성."""

import numpy as np

import forge3d as f3d

ew = f3d.EntityWorld()

# 정적 지면
ew.create_entity(
    f3d.Transform(position=np.array([0.0, 0.0, 0.0])),
    f3d.Collider(shape="box", size=np.array([20.0, 20.0, 0.1])),
    f3d.Rigidbody(is_static=True),
)

# 낙하하는 박스
box = ew.create_entity(
    f3d.Transform(position=np.array([0.0, 0.0, 5.0])),
    f3d.MeshRenderer(mesh_id="box_1x1x1", material_id="red"),
    f3d.Rigidbody(mass=1.0),
)


# 스크립트: 쿼리로 박스 위치 출력
def on_update(dt: float) -> None:
    for _e, tf in ew.query(f3d.Transform, f3d.Rigidbody):
        if not tf.rotation[0]:  # type: ignore[index]
            pass  # 위치 출력은 주석처리 (자동 테스트용)


ew.create_entity(f3d.Script(on_update=on_update))
ew.add_system(f3d.ScriptSystem())

# 10 스텝 시뮬레이션 (렌더 없음, 헤드리스)
render_sys = f3d.RenderSystem()
ew.add_system(render_sys)
for _ in range(10):
    ew.step(1 / 60)

snap = render_sys.last_snapshot
print(f"ECS 씬: {len(snap.bodies) if snap else 0}개 바디 렌더 스냅샷 생성")
print("05_ecs_scene 완료!")
