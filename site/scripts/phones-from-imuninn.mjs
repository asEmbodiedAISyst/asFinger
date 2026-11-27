#!/usr/bin/env node
// Writes src/data/phones.json, the phones offered in the editor's camera group, from iMuninn's phone data.
//
//   node scripts/phones-from-imuninn.mjs path/to/imuninn/protocol/frames/iphone-frames.json [imuninn-commit]
//
// iMuninn (github.com/Bardreamaster/imuninn, protocol/frames/iphone-frames.json, also shipped as
// imuninn/data/iphone-frames.json in the Python package) reads Apple's Accessory Design Guidelines dimensional
// drawings into one table per model, in the frame convention asFinger follows: `device` = centre of the display
// active area on the front glass, x right, y to the top, z out of the screen; lengths in mm.
//
// What is converted here, to the parameters of hardware/configs/iphone17pro_default.json, whose P_phone is the same
// `device` frame:
//   * outline_x / outline_y = centre of the phone outline in `device` (0 to 0.005 mm on these models);
//   * corner_r = corner radius of the outline seen from the back: 0.15 x the short side, iMuninn's glb estimate (Apple
//     does not dimension it);
//   * bump_h = height of the rear camera cover glass above the back (`camera_glass` on the drawing: plateau + glass);
//   * magsafe_x / magsafe_y = centre of the MagSafe circle, where the holder sits;
//   * telephoto / lidar = whether the drawing has them (config options of the same name).
// The file is committed; run this again when the iMuninn data changes.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

// iMuninn model slug -> editor item id. Order = order in the editor.
const MODELS = {
  'iphone-18-pro': 'iphone18pro',
  'iphone-17-pro': 'iphone17pro',
  'iphone-17': 'iphone17',
  'iphone-16-pro': 'iphone16pro',
  'iphone-15-pro': 'iphone15pro',
  'iphone-14-pro': 'iphone14pro',
};

const [src, commit] = process.argv.slice(2);
if (!src) {
  console.error('usage: node scripts/phones-from-imuninn.mjs path/to/iphone-frames.json [imuninn-commit]');
  process.exit(2);
}
const data = JSON.parse(readFileSync(src, 'utf8'));
if (data.frame_convention !== 1 || data.units !== 'mm') throw new Error(`unexpected iMuninn data: frame_convention ${data.frame_convention}, units ${data.units}`);

const r3 = (v) => Math.round(v * 1000) / 1000;
const phones = [];
for (const [slug, id] of Object.entries(MODELS)) {
  const m = data.models[slug];
  if (!m) throw new Error(`${slug} is not in ${src}`);
  const o = m.outline, a = m.display_active_area;
  // display centre in the outline frame (x right, y up, seen from the front); the outline centre in `device` is minus that
  const dx = a.left + a.width / 2 - o.width / 2, dy = -(a.top + a.height / 2 - o.height / 2);
  const f = m.frames, c = m.cameras, ex = m.extras ?? {};
  const main = f.cam_main_optical;
  const sets = {
    phone_W: o.width, phone_L: o.height, phone_t: o.thickness, outline_x: r3(-dx) + 0, outline_y: r3(-dy) + 0,
    lens_x: main.origin[0], lens_y: main.origin[1],
    bump_h: r3(-main.origin[2] - o.thickness),
    ring_D: c.main.window_diameter,
    corner_r: r3(0.15 * Math.min(o.width, o.height)), // not dimensioned by Apple; iMuninn's glb estimate
  };
  const put = (name, p) => { if (p) [sets[`${name}_x`], sets[`${name}_y`]] = [p[0], p[1]]; };
  put('uw', f.cam_ultra_wide_optical?.origin);
  put('tele', f.cam_telephoto_optical?.origin);
  put('front', f.cam_front_optical?.origin);
  put('lidar', ex.lidar?.position_in_body);
  put('flash', ex.flash?.position_in_body);
  put('magsafe', f.magsafe?.origin);
  phones.push({
    id, slug, name: m.name, identifiers: m.identifiers,
    sets,
    options: { telephoto: !!f.cam_telephoto_optical, lidar: !!ex.lidar },
    camera_plateau: m.rear_heights_from_back?.camera_plateau ?? null,
    front_estimated: f.cam_front_optical?.provenance === 'estimated',
    cones_deg: Object.fromEntries(Object.entries(c).filter(([, v]) => v.keepout_cone_deg).map(([k, v]) => [k, v.keepout_cone_deg])),
    drawing: { url: m.drawing.url, date: m.drawing.sheet_date },
    review: m.review?.dimensions ?? 'auto',
  });
}

const out = {
  source: 'iMuninn protocol/frames/iphone-frames.json (Apple Accessory Design Guidelines dimensional drawings); written by scripts/phones-from-imuninn.mjs',
  imuninn_commit: commit ?? null,
  phones,
};
const dest = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'data', 'phones.json');
writeFileSync(dest, JSON.stringify(out, null, 1) + '\n');
console.log(`${dest}: ${phones.length} phones`);
