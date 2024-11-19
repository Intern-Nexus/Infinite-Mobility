# Copyright (C) 2023, Princeton University.
# This source code is licensed under the BSD 3-Clause license found in the LICENSE file in the root directory
# of this
# source tree.

# Authors:
# - Lingjie Mei
# - Alex Raistrick
# - Karhan Kayan - add fire option

import argparse
import importlib
import logging
import math
import os
import random
import re
import subprocess
import sys
import traceback
from itertools import product
from multiprocessing import Pool
from pathlib import Path

# from torch.multiprocessing import Pool
# # from multiprocessing import Pool
# import torch.multiprocessing as mp
# # mp.set_start_method('spawn', force=True)
# context = mp.get_context("spawn")
# Pool = context.Pool
# ORIG_SYS_PATH = list(sys.path)
# from torch.multiprocessing import current_process
# if current_process().name == 'MainProcess':
#     import bpy
# BPY_SYS_PATH = list(sys.path)
import bpy
import gin
import numpy as np
import submitit
from PIL import Image

# ruff: noqa: E402
# NOTE: logging config has to be before imports that use logging
logging.basicConfig(
    format="[%(asctime)s.%(msecs)03d] [%(module)s] [%(levelname)s] | %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)

import infinigen
from infinigen.assets.lighting import (
    hdri_lighting,
    holdout_lighting,
    sky_lighting,
    three_point_lighting,
)

# from infinigen.core.rendering.render import enable_gpu
from infinigen.assets.utils.decorate import read_base_co, read_co
from infinigen.assets.utils.misc import assign_material, subclasses
from infinigen.core import init, surface
from infinigen.core.init import configure_cycles_devices
from infinigen.core.placement import AssetFactory, density
from infinigen.core.tagging import tag_system

# noinspection PyUnresolvedReferences
from infinigen.core.util import blender as butil
from infinigen.core.util.camera import points_inview
from infinigen.core.util.math import FixedSeed
from infinigen.core.util.test_utils import load_txt_list
from infinigen.tools import export

logging.basicConfig(
    format="[%(asctime)s.%(msecs)03d] [%(name)s] [%(levelname)s] | %(message)s",
    datefmt="%H:%M:%S",
    level=logging.WARNING,
)

logger = logging.getLogger(__name__)

OBJECTS_PATH = infinigen.repo_root() / "infinigen/assets/objects"
assert OBJECTS_PATH.exists(), OBJECTS_PATH


def build_scene_asset(args, factory_name, idx, path):
    fac = None
    for subdir in sorted(list(OBJECTS_PATH.iterdir())):
        clsname = subdir.name.split(".")[0].strip()
        with gin.unlock_config():
            module = importlib.import_module(f"infinigen.assets.objects.{clsname}")
        if hasattr(module, factory_name):
            fac = getattr(module, factory_name)
            logger.info(f"Found {factory_name} in {subdir}")
            break
        logger.debug(f"{factory_name} not found in {subdir}")
    if fac is None:
        raise ModuleNotFoundError(f"{factory_name} not Found.")

    if args.dryrun:
        return

    with FixedSeed(idx):
        fac = fac(idx)
        try:
            if args.spawn_placeholder:
                ph = fac.spawn_placeholder(idx, (0, 0, 0), (0, 0, 0))
                asset = fac.spawn_asset(idx, path, placeholder=ph)
            else:
                asset = fac.spawn_asset(idx, path)
        except Exception as e:
            traceback.print_exc()
            print(f"{fac}.spawn_asset({idx=}) FAILED!! {e}")
            raise e
        fac.finalize_assets(asset)
        if args.fire:
            from infinigen.assets.fluid.fluid import set_obj_on_fire

            set_obj_on_fire(
                asset,
                0,
                resolution=args.fire_res,
                simulation_duration=args.fire_duration,
                noise_scale=2,
                add_turbulence=True,
                adaptive_domain=False,
            )
            bpy.context.scene.frame_set(args.fire_duration)
            bpy.context.scene.frame_end = args.fire_duration
            bpy.data.worlds["World"].node_tree.nodes["Background.001"].inputs[
                1
            ].default_value = 0.04
            bpy.context.scene.view_settings.exposure = -1
        bpy.context.view_layer.objects.active = asset
        parent = asset
        if asset.type == "EMPTY":
            meshes = [o for o in asset.children_recursive if o.type == "MESH"]
            sizes = []
            for m in meshes:
                co = read_co(m)
                sizes.append((np.amax(co, 0) - np.amin(co, 0)).sum())
            i = np.argmax(np.array(sizes))
            asset = meshes[i]
        if not args.no_mod:
            if parent.animation_data is not None:
                drivers = parent.animation_data.drivers.values()
                for d in drivers:
                    parent.driver_remove(d.data_path)
            co = read_co(asset)
            x_min, x_max = np.amin(co, 0), np.amax(co, 0)
            parent.location = -(x_min[0] + x_max[0]) / 2, -(x_min[1] + x_max[1]) / 2, 0
            butil.apply_transform(parent, loc=True)
            if not args.no_ground:
                bpy.ops.mesh.primitive_grid_add(
                    size=5, x_subdivisions=400, y_subdivisions=400
                )
                plane = bpy.context.active_object
                plane.location[-1] = x_min[-1]
                plane.is_shadow_catcher = True
                material = bpy.data.materials.new("plane")
                material.use_nodes = True
                material.node_tree.nodes["Principled BSDF"].inputs[0].default_value = (
                    0.015,
                    0.009,
                    0.003,
                    1,
                )
                assign_material(plane, material)

    return asset


def build_scene_surface(args, factory_name, idx):
    try:
        with gin.unlock_config():
            scatter = importlib.import_module(
                f"infinigen.assets.scatters.{factory_name}"
            )

            if not hasattr(scatter, "apply"):
                raise ValueError(f"{scatter} has no apply()")

            if args.dryun:
                return

            bpy.ops.mesh.primitive_grid_add(
                size=10, x_subdivisions=400, y_subdivisions=400
            )
            plane = bpy.context.active_object

            material = bpy.data.materials.new("plane")
            material.use_nodes = True
            material.node_tree.nodes["Principled BSDF"].inputs[0].default_value = (
                0.015,
                0.009,
                0.003,
                1,
            )
            assign_material(plane, material)
            if type(scatter) is type:
                scatter = scatter(idx)
            scatter.apply(plane, selection=density.placement_mask(0.15, 0.45))
            asset = plane
    except ModuleNotFoundError:
        try:
            with gin.unlock_config():
                try:
                    template = importlib.import_module(
                        f"infinigen.assets.materials.{factory_name}"
                    )
                except ImportError:
                    for subdir in os.listdir("infinigen/assets/materials"):
                        with gin.unlock_config():
                            module = importlib.import_module(
                                f'infinigen.assets.materials.{subdir.split(".")[0]}'
                            )
                        if hasattr(module, factory_name):
                            template = getattr(module, factory_name)
                            break
                    else:
                        raise Exception(f"{factory_name} not Found.")

                if args.dryrun:
                    return

                if hasattr(template, "make_sphere"):
                    asset = template.make_sphere()
                else:
                    bpy.ops.mesh.primitive_ico_sphere_add(radius=0.8, subdivisions=9)
                    asset = bpy.context.active_object
                if type(template) is type:
                    template = template(idx)
                template.apply(asset)
        except ModuleNotFoundError:
            raise Exception(f"{factory_name} not Found.")

    return asset


def build_and_save_asset(payload: dict):
    # unpack payload - args are packed into payload for compatibility with slurm/multiprocessing
    factory_name = payload["fac"]
    args = payload["args"]
    idx = payload["idx"]

    logger.info(f"Building scene for {factory_name} {idx}")

    if args.seed > 0:
        idx = args.seed

    path = args.output_folder / factory_name
    if (path / f"images/image_{idx:03d}.png").exists() and args.skip_existing:
        print(f"Skipping {path}")
        return
    if (path / f"{idx}").exists():
        return
    path.mkdir(exist_ok=True)

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.render.resolution_x, scene.render.resolution_y = map(
        int, args.resolution.split("x")
    )
    scene.cycles.samples = args.samples
    butil.clear_scene()

    if not args.fire:
        bpy.context.scene.render.film_transparent = args.film_transparent
        bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value[
            -1
        ] = 0
    camera, center = setup_camera(args)

    if "Factory" in factory_name:
        asset = build_scene_asset(args, factory_name, idx, path)
    else:
        asset = build_scene_surface(args, factory_name, idx, path)

    if args.dryrun:
        return
    return
    configure_cycles_devices()

    with FixedSeed(args.lighting + idx):
        if args.hdri:
            hdri_lighting.add_lighting()
        elif args.three_point:
            holdout_lighting.add_lighting()
            three_point_lighting.add_lighting(asset)
        else:
            sky_lighting.add_lighting(camera)
            nodes = bpy.data.worlds["World"].node_tree.nodes
            sky_texture = [n for n in nodes if n.name.startswith("Sky Texture")][-1]
            sky_texture.sun_elevation = np.deg2rad(args.elevation)
            sky_texture.sun_rotation = np.pi * 0.75

    if args.scale_reference:
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.3, depth=1.8, location=(4.9, 4.9, 1.8 / 2)
        )

    if args.cam_center > 0 and asset:
        co = read_base_co(asset) + asset.location
        center.location = (np.amin(co, 0) + np.amax(co, 0)) / 2
        center.location[-1] += args.cam_zoff

    if args.cam_dist <= 0 and asset:
        if "Factory" in factory_name:
            adjust_cam_distance(asset, camera, args.margin)
        else:
            adjust_cam_distance(asset, camera, args.margin, 0.75)

    cam_info_ng = bpy.data.node_groups.get("nodegroup_active_cam_info")
    if cam_info_ng is not None:
        cam_info_ng.nodes["Object Info"].inputs["Object"].default_value = camera

    if args.save_blend:
        (path / "scenes").mkdir(exist_ok=True)
        butil.save_blend(f"{path}/scenes/scene_{idx:03d}.blend", autopack=True)
        tag_system.save_tag(f"{path}/MaskTag.json")

    if args.fire:
        bpy.data.worlds["World"].node_tree.nodes["Background.001"].inputs[
            1
        ].default_value = 0.04
        bpy.context.scene.view_settings.exposure = -2

    if args.render == "image":
        (path / "images").mkdir(exist_ok=True)
        imgpath = path / f"images/image_{idx:03d}.png"
        scene.render.filepath = str(imgpath)
        # bpy.ops.render.render(write_still=True)
    elif args.render == "video":
        bpy.context.scene.frame_end = args.frame_end
        parent(asset).driver_add("rotation_euler")[
            -1
        ].driver.expression = f"frame/{args.frame_end / (2 * np.pi * args.cycles)}"
        (path / "frames" / f"scene_{idx:03d}").mkdir(parents=True, exist_ok=True)
        imgpath = path / f"frames/scene_{idx:03d}/frame_###.png"
        scene.render.filepath = str(imgpath)
        bpy.ops.render.render(animation=True)
    elif args.render == "none":
        pass
    else:
        raise ValueError(f"Unrecognized {args.render=}")

    if args.export is not None:
        export_path = path / "export" / f"export_{idx:03d}"
        export_path.mkdir(exist_ok=True, parents=True)
        export.export_curr_scene(
            export_path, format=args.export, image_res=args.export_texture_res
        )


def build_and_save_asset_for_loop(payloads: list):
    # Initialize CUDA in the worker
    # if torch.cuda.is_available():
    #     try:
    #         device = torch.device("cuda:0")  # Initialize your GPU device
    # torch.cuda.init()  # Initialize CUDA if necessary
    # except RuntimeError as e:
    #     print(f"CUDA initialization error: {e}")
    #     return None  # Handle the error appropriately

    for payload in payloads:
        # print(payload)
        build_and_save_asset(payload)


def parent(obj):
    return obj if obj.parent is None else obj.parent


def adjust_cam_distance(asset, camera, margin, percent=0.999):
    co = read_base_co(asset) * asset.scale
    co += asset.location
    lowest = np.amin(co, 0)
    highest = np.amax(co, 0)
    interp = np.linspace(lowest, highest, 11)
    bbox = np.array(list(product(*zip(*interp))))
    for cam_dist in np.exp(np.linspace(-1.0, 5.5, 500)):
        camera.location[1] = -cam_dist
        bpy.context.view_layer.update()
        inview = points_inview(bbox, camera)
        if inview.sum() / inview.size >= percent:
            camera.location[1] *= 1 + margin
            bpy.context.view_layer.update()
            break
    else:
        camera.location[1] = -6


def make_grid(args, path, n):
    files = []
    for filename in sorted(os.listdir(f"{path}/images")):
        if filename.endswith(".png"):
            files.append(f"{path}/images/{filename}")
    files = files[:n]
    if len(files) == 0:
        print("No images found")
        return
    with Image.open(files[0]) as i:
        x, y = i.size
    for i, name in enumerate([path.stem, f"{path.stem}_"]):
        if args.zoom:
            img = Image.new("RGBA", (2 * x, y))
            sz = int(np.floor(np.sqrt(n - 0.9)))
            if i > 0:
                random.shuffle(files)
            with Image.open(files[0]) as i:
                img.paste(i, (0, 0))
            for idx in range(sz**2):
                with Image.open(files[min(idx + 1, len(files) - 1)]) as i:
                    img.paste(
                        i.resize((x // sz, y // sz)),
                        (x + (idx % sz) * (x // sz), idx // sz * (y // sz)),
                    )
            img.save(f"{path}/{name}.png")
        else:
            sz_x = list(
                sorted(
                    range(1, n + 1),
                    key=lambda x: abs(math.ceil(n / x) / x - args.best_ratio),
                )
            )[0]
            sz_y = math.ceil(n / sz_x)
            img = Image.new("RGBA", (sz_x * x, sz_y * y))
            if i > 0:
                random.shuffle(files)
            for idx, file in enumerate(files):
                with Image.open(file) as i:
                    img.paste(i, (idx % sz_x * x, idx // sz_x * y))
            img.save(f"{path}/{name}.png")
        print(f"{path}/{name}.png generated")


def setup_camera(args):
    cam_dist = args.cam_dist if args.cam_dist > 0 else 6
    bpy.ops.object.camera_add(location=(0, -cam_dist, 0), rotation=(np.pi / 2, 0, 0))
    camera = bpy.context.active_object
    camera.parent = butil.spawn_empty("Camera parent")
    camera.parent.location = (0, 0, args.cam_zoff)
    camera.parent.rotation_euler = np.deg2rad(np.array(args.cam_angle))
    bpy.data.scenes["Scene"].camera = camera
    scene = bpy.context.scene
    camera.data.sensor_height = (
        camera.data.sensor_width * scene.render.resolution_y / scene.render.resolution_x
    )
    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            area.spaces.active.region_3d.view_perspective = "CAMERA"
            break
    cam_info_ng = bpy.data.node_groups.get("nodegroup_active_cam_info")
    if cam_info_ng is not None:
        cam_info_ng.nodes["Object Info"].inputs["Object"].default_value = camera
    return camera, camera.parent


def mapfunc(f, its, args):
    if args.n_workers == 1:
        return [f(i) for i in its]
    elif not args.slurm:
        with Pool(args.n_workers) as p:
            return list(p.imap(f, its))

    else:
        executor = submitit.AutoExecutor(folder=args.output_folder / "logs")
        executor.update_parameters(
            name=args.output_folder.name,
            timeout_min=60,
            cpus_per_task=2,
            mem_gb=8,
            slurm_partition=os.environ["INFINIGEN_SLURMPARTITION"],
            slurm_array_parallelism=args.n_workers,
        )
        jobs = executor.map_array(f, its)
        for j in jobs:
            print(f"Job finished {j.wait()}")


def main(args):
    bpy.context.window.workspace = bpy.data.workspaces["Geometry Nodes"]

    init.apply_gin_configs(
        ["infinigen_examples/configs_indoor", "infinigen_examples/configs_nature"],
        skip_unknown=True,
    )
    surface.registry.initialize_from_gin()

    if args.debug is not None:
        for name in logging.root.manager.loggerDict:
            if not name.startswith("infinigen"):
                continue
            if len(args.debug) == 0 or any(name.endswith(x) for x in args.debug):
                logging.getLogger(name).setLevel(logging.DEBUG)

    init.configure_blender()

    if args.gpu:
        init.configure_render_cycles()

    if ".txt" in args.factories[0]:
        name = args.factories[0].split(".")[-2].split("/")[-1]
    else:
        name = "_".join(args.factories)

    if args.output_folder is None:
        args.output_folder = Path(os.getcwd()) / "outputs"

    path = Path(args.output_folder) / name
    path.mkdir(exist_ok=True, parents=True)

    factories = list(args.factories)

    if "ALL_ASSETS" in factories:
        factories += [f.__name__ for f in subclasses(AssetFactory)]
        factories.remove("ALL_ASSETS")
        logger.warning(
            "ALL_ASSETS is deprecated. Use `-f tests/assets/list_nature_meshes.txt` and `-f tests/assets/list_indoor_meshes.txt` instead."
        )
    if "ALL_SCATTERS" in factories:
        factories += [f.stem for f in Path("infinigen/assets/scatters").iterdir()]
        factories.remove("ALL_SCATTERS")
    if "ALL_MATERIALS" in factories:
        factories += [f.stem for f in Path("infinigen/assets/materials").iterdir()]
        factories.remove("ALL_MATERIALS")
        logger.warning(
            "ALL_MATERIALS is deprecated. Use `-f tests/assets/list_nature_materials.txt` and `-f tests/assets/list_indoor_materials.txt` instead."
        )

    has_txt = ".txt" in factories[0]
    if has_txt:
        factories = [
            f.split(".")[-1] for f in load_txt_list(factories[0], skip_sharp=False)
        ]

    if not args.postprocessing_only:
        for fac in factories:
            if args.start_seed > 0:
                start_seed = args.start_seed
            else:
                start_seed = 0
            targets = [{"args": args, "fac": fac, "idx": idx} for idx in range(start_seed, start_seed + args.n_images)]
            if args.sep_batches > 1:
                # import multiprocessing
                # multiprocessing.set_start_method("spawn")
                batch_size = args.n_images // args.sep_batches
                chunked_targets = []
                chunk_idx = 0
                for _ in range(args.sep_batches):
                    chunked_targets.append(targets[chunk_idx : chunk_idx + batch_size])
                    chunk_idx += batch_size
                mapfunc(build_and_save_asset_for_loop, chunked_targets, args)
            else:
                mapfunc(build_and_save_asset, targets, args)

    if args.dryrun:
        return

    for j, fac in enumerate(factories):
        break
        fac_path = args.output_folder / fac
        fac_path.mkdir(exist_ok=True, parents=True)

        f"{fac_path} does not exist"
        if has_txt:
            for i in range(args.n_images):
                img_path = fac_path / "images" / f"image_{i:03d}.png"
                if img_path.exists():
                    subprocess.run(
                        f"cp -f {img_path} {path}/{fac}_{i:03d}.png", shell=True
                    )
                else:
                    print(f"{img_path} does not exist")
        elif args.render == "image":
            make_grid(args, fac_path, args.n_images)
        elif args.render == "video":
            (fac_path / "videos").mkdir(exist_ok=True)
            for i in range(args.n_images):
                subprocess.run(
                    f'ffmpeg -y -r 24 -pattern_type glob -i "{fac_path}/frames/scene_{i:03d}/frame*.png" '
                    f"{fac_path}/videos/video_{i:03d}.mp4",
                    shell=True,
                )


def snake_case(s):
    return "_".join(
        re.sub(
            "([A-Z][a-z]+)", r" \1", re.sub("([A-Z]+)", r" \1", s.replace("-", " "))
        ).split()
    ).lower()


def make_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output_folder", type=Path, default=None)
    parser.add_argument(
        "-f",
        "--factories",
        default=[],
        nargs="+",
        help="List factories/surface scatters/surface materials you want to render",
    )
    parser.add_argument(
        "-n", "--n_images", default=1, type=int, help="Number of scenes to render"
    )
    parser.add_argument(
        "-m",
        "--margin",
        default=0.01,
        help="Margin between the asset the boundary of the image when automatically adjusting "
        "the camera",
    )
    parser.add_argument(
        "-R",
        "--resolution",
        default="1024x1024",
        type=str,
        help="Image resolution widthxheight",
    )
    parser.add_argument(
        "-p", "--samples", default=200, type=int, help="Blender cycles samples"
    )
    parser.add_argument("-l", "--lighting", default=0, type=int, help="Lighting seed")
    parser.add_argument(
        "-Z",
        "--cam_zoff",
        "--z_offset",
        type=float,
        default=0.0,
        help="Additional offset on Z axis for camera look-at positions",
    )
    parser.add_argument(
        "-s", "--save_blend", action="store_true", help="Whether to save .blend file"
    )
    parser.add_argument(
        "-e", "--elevation", default=60, type=float, help="Elevation of the sun"
    )
    parser.add_argument(
        "--cam_dist",
        default=0,
        type=float,
        help="Distance from the camera to the look-at position",
    )
    parser.add_argument(
        "-a",
        "--cam_angle",
        default=(-30, 0, 45),
        type=float,
        nargs="+",
        help="Camera rotation in XYZ",
    )
    parser.add_argument(
        "-O",
        "--offset",
        default=(0, 0, 0),
        type=float,
        nargs="+",
        help="asset location",
    )
    parser.add_argument(
        "-c", "--cam_center", default=1, type=int, help="Camera rotation in XYZ"
    )
    parser.add_argument(
        "-r",
        "--render",
        default="image",
        type=str,
        choices=["image", "video", "none"],
        help="Whether to render the scene in images or video",
    )
    parser.add_argument(
        "-b",
        "--best_ratio",
        default=9 / 16,
        type=float,
        help="Best aspect ratio for compiling the images into asset grid",
    )
    parser.add_argument("-F", "--fire", action="store_true")
    parser.add_argument("-I", "--fire_res", default=100, type=int)
    parser.add_argument("-U", "--fire_duration", default=30, type=int)
    parser.add_argument(
        "-t",
        "--film_transparent",
        default=1,
        type=int,
        help="Whether the background is transparent",
    )
    parser.add_argument(
        "-E", "--frame_end", type=int, default=120, help="End of frame in videos"
    )
    parser.add_argument(
        "-g", "--gpu", action="store_true", help="Whether to use gpu in rendering"
    )
    parser.add_argument(
        "-C", "--cycles", type=float, default=1, help="render video cycles"
    )
    parser.add_argument(
        "-A", "--scale_reference", action="store_true", help="Add the scale reference"
    )
    parser.add_argument(
        "-S",
        "--skip_existing",
        action="store_true",
        help="Skip existing scenes and renders",
    )
    parser.add_argument(
        "-P",
        "--postprocessing_only",
        action="store_true",
        help="Only run postprocessing",
    )
    parser.add_argument(
        "-D", "--seed", type=int, default=-1, help="Run a specific seed."
    )
    parser.add_argument("-N", "--no-mod", action="store_true", help="No modification")
    parser.add_argument("-H", "--hdri", action="store_true", help="add_hdri")
    parser.add_argument(
        "-T", "--three_point", action="store_true", help="add three-point lighting"
    )
    parser.add_argument("-G", "--no_ground", action="store_true", help="no ground")
    parser.add_argument(
        "-W", "--spawn_placeholder", action="store_true", help="spawn placeholder"
    )
    parser.add_argument("-z", "--zoom", action="store_true", help="zoom first figure")

    parser.add_argument("--n_workers", type=int, default=1)
    parser.add_argument("--slurm", action="store_true")

    parser.add_argument(
        "--export", type=str, default=None, choices=export.FORMAT_CHOICES
    )
    parser.add_argument("--export_texture_res", type=int, default=1024)
    parser.add_argument("-d", "--debug", type=str, nargs="*", default=None)
    parser.add_argument(
        "--dryrun",
        action="store_true",
        help="Import assets but do not run them. Used for testing.",
    )
    parser.add_argument(
        "--sep_batches",
        type=int,
        default=1,
        help="Separate for multi-processing",
    )
    parser.add_argument(
        "--start_seed",
        type=int,
        default=-1,
        help="Separate for multi-processing",
    )

    return init.parse_args_blender(parser)


if __name__ == "__main__":
    args = make_args()
    args.no_mod = args.no_mod or args.fire
    args.film_transparent = args.film_transparent and not args.hdri
    with FixedSeed(1):
        main(args)
