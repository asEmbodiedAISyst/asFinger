# Seeed's official reBot B601-RS meshes (not kept in this repository)

Get them with

    uv run python sim/fetch_arm_meshes.py

which downloads, unmodified, from https://github.com/Seeed-Projects/reBot-DevArm at commit
`e0a06261f0c38a42e044821476b4ad664cb289ed` (main on 2026-11-26), folder `Rebot_Arm_description/RS/meshes/`
(`base_link`, `link1`, `link6` from `shared/`, the rest from `visual/`), plus the repository's `LICENSE`
(CERN-OHL-W-2.0), and checks every file against `SHA256SUMS` here. Only this file and `SHA256SUMS` are in git
(`.gitignore`); the meshes are not redistributed.

18 parts, 617 k faces, 30 MB, not decimated. Frames are the URDF link frames (`ReBot_Arm_RS.urdf`); `base_link` includes
the black base plate (140 x 200 x 10 mm), whose underside is the base frame's z = 0. In the twin they are drawn only;
they do not collide.
