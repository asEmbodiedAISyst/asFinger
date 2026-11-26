# Design decisions

Each entry gives a decision and its reason.

## One config for all outputs

The printed part, the simulation model and the robot program must agree on where the TCP and the camera are. If each of them is made by hand, they drift apart. One config is the source of all of them, so a change of a parameter reaches every output.

## Frames are named and explicit

Each interface of the tool is a frame with a name: the flange, the mounting face, the TCP, the phone, each camera. The outputs carry these frames: sites in the MJCF file, entries in `resolved.json`. A user reads the TCP offset from the model and does not measure it on the part.

## Shapes are simple solids with union and difference

MuJoCo describes collision geometry with boxes, spheres and cylinders. The config uses the same shapes, so the collision model comes from the config without a second description. Union and difference of these shapes are sufficient for the pusher, and they are easy to rebuild in other programs. Imported meshes exist for the parts that are not simple, such as the phone holder.

## The core is pure Python

`geom`, `expr`, `frames`, `csg`, `options`, `interference` and `mjcf` use only the standard library. They therefore run unchanged in Pyodide in the browser, and in the Python interpreter of a CAD program. numpy and manifold3d are needed only to make meshes.

## The browser runs the same Python

The editor does not have its own implementation of parameters, frames and solvers in TypeScript. It runs the package in Pyodide. The cost is a download of about 13 MB on the first load. The gain is that a config has the same result in the editor and on the command line. Only the mesh step exists twice (`mesh.py` and `csg.ts`): the browser calls the WebAssembly build of Manifold directly.

## Expressions are evaluated with a whitelist

A config can come from another person or from the editor. `expr.py` parses an expression with `ast` and permits only numbers, names, arithmetic, comparisons, a conditional and a fixed list of functions. It never calls `eval`.

## Solved frames store their result

The phone pose comes from a solver. The config stores the result with a hash of the inputs. A build uses the stored result and warns when it is stale. A build therefore does not change when the solver code changes, and a printed version can be rebuilt exactly. The cost is that a user must add `--resolve` after a parameter change. The editor always solves again, because it is interactive.

## Screw holes stay in the robot frame

The holes of the pusher base are cut in `F_robot`, not in the frame of the pusher. When the mounting angle changes, the holes stay on the pattern of the flange and the pusher turns above them. Any mounting angle can therefore be printed for a given flange.

## Options prune, they do not edit

An option removes frames and all that depends on them from a view of the config. The file itself keeps everything. A user can therefore switch the phone off and on without loss of data, and a config exported from the editor is always complete.

## Checks are data in the config

Limits and interference rules are written in the config, with their messages. The generator and the editor read the same rules. A new tool variant brings its own rules, and the code does not change.

## STL files are written in the frame of the part

A printed part is written in its own frame, and a print set in the frame of its first part. For the pusher this puts the mounting face on z = 0, which is the face that goes on the print bed. The meshes for MuJoCo are written in the body frame of the MJCF file.

## The site is static

The landing page, the editor and the documentation are static files. The editor computes in the browser. The site therefore runs on GitHub Pages without a server, and nothing that a user enters leaves the browser.
