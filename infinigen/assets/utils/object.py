# Copyright (C) 2023, Princeton University.
# This source code is licensed under the BSD 3-Clause license found in the LICENSE file in the root directory
# of this source tree.

# Authors: Lingjie Mei
import glob
import json
import os
from pathlib import Path
from math import radians
from mathutils import Matrix

import bpy
import numpy as np
#import torch
import trimesh
from mathutils import Vector
from tqdm import tqdm

# from pytorch3d.io import load_obj
# from pytorch3d.structures import Meshes
# from pytorch3d.ops import sample_points_from_meshes
# from bpy_lib import *
# from pytorch3d.io import load_ply, save_ply
import infinigen.core.util.blender as butil
from infinigen.assets.utils.decorate import read_co
from infinigen.core.util.blender import select_none

import urdfpy

# def sample_and_save_points(verts, faces, path, num_samples=50000, return_normals=True):

#     meshes = Meshes(verts=[verts], faces=[faces])
#     samples, normals = sample_points_from_meshes(
#         meshes,
#         num_samples = num_samples,
#         return_normals = return_normals,
#         return_textures = False,
#     )

#     samples = samples.squeeze(0)
#     normals = normals.squeeze(0)
#     np.savez(f'{path}.npz', points=samples.cpu().numpy(), normals=normals.cpu().numpy())


# def write_json(data_path, json_path, idx=None, names=None, category=None):
#     # case_list = os.listdir(data_path)
#     # case_list_int = [int(case) for case in case_list]
#     # case_list_int.sort()
#     # case_list =[str(case) for case in case_list_int]
#     # for case in tqdm(case_list):
#     infos = []
#     info_case = {}
#     info_case["id"] = idx

#     for i, name in enumerate(names):
#         obj_name = name

#         info_case["obj_name"] = obj_name
#         info_case["category"] = category
#         info_case["file_obj_path"] = os.path.join(data_path, f"{idx}/objs/whole.obj")
#         info_case["file_pcd_path"] = os.path.join(
#             data_path, f"{idx}/point_cloud/whole.npz"
#         )
#         info_parts = []

#         for result_part_info in result_parts_info:
#             part_info = {}
#             part_info["part_name"] = obj_name + "_part"
#             part_info["file_name"] = str(result_part_info["id"]) + ".obj"
#             part_info["file_obj_path"] = os.path.join(
#                 data_path, f"{idx}/objs/{str(result_part_info['id'])}.obj"
#             )
#             part_info["file_pcd_path"] = os.path.join(
#                 data_path, f"{idx}/point_cloud/{str(result_part_info['id'])}.npz"
#             )
#             info_parts.append(part_info)
#         info_case["part"] = info_parts
#         infos.append(info_case)

#     with open(f"{json_path}/data_infos.json", "w") as f:
#         json.dump(infos, f, indent=2)

robot_tree = {}
root = None


def center(obj):
    return (Vector(obj.bound_box[0]) + Vector(obj.bound_box[-2])) * obj.scale / 2.0


def origin2lowest(obj, vertical=False, centered=False, approximate=False):
    co = read_co(obj)
    if not len(co):
        return
    i = np.argmin(co[:, -1])
    if approximate:
        indices = np.argsort(co[:, -1])
        obj.location = -np.mean(co[indices[: len(co) // 10]], 0)
        obj.location[-1] = -co[i, -1]
    elif centered:
        obj.location = -center(obj)
        obj.location[-1] = -co[i, -1]
    elif vertical:
        obj.location[-1] = -co[i, -1]
    else:
        obj.location = -co[i]
    butil.apply_transform(obj, loc=True)


def origin2highest(obj):
    co = read_co(obj)
    i = np.argmax(co[:, -1])
    obj.location = -co[i]
    butil.apply_transform(obj, loc=True)


def origin2leftmost(obj):
    co = read_co(obj)
    i = np.argmin(co[:, 0])
    obj.location = -co[i]
    butil.apply_transform(obj, loc=True)


def data2mesh(vertices=(), edges=(), faces=(), name=""):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, edges, faces)
    mesh.update()
    return mesh


def mesh2obj(mesh):
    obj = bpy.data.objects.new(mesh.name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    return obj


def trimesh2obj(trimesh):
    obj = butil.object_from_trimesh(trimesh, "")
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    return obj


def obj2trimesh(obj):

# set the new_obj as active object for later process
    bpy.context.view_layer.objects.active = obj

# make sure new_obj has single user copy
    bpy.ops.object.make_single_user(object=True, obdata=True, material=False, animation=False)
    butil.modify_mesh(obj, "TRIANGULATE", min_vertices=3)
    vertices = read_co(obj)
    arr = np.zeros(len(obj.data.polygons) * 3)
    obj.data.polygons.foreach_get("vertices", arr)
    faces = arr.reshape(-1, 3)
    return trimesh.Trimesh(vertices, faces)


def obj2trimesh_and_save(obj, path=None, idx="unknown", is_return=False):
    trimesh_object = obj2trimesh(obj)
    if idx == "unknown":
        idx = f"random_{np.random.randint(0, 10000)}"
    else:
        idx = str(idx)
    if path is None:
        path = os.path.join(os.path.curdir, "outputs")
    if not os.path.exists(path):
        os.mkdir(path)
    if not isinstance(path, Path):
        path = Path(path)
    (path / ("parts_seed_" + idx)).mkdir(exist_ok=True)
    # File path for saving the .obj file
    file_path = os.path.join(
        path, "parts_seed_" + idx, f"{obj.name}_part_{int(idx)+1}.obj"
    )
    trimesh_object.export(file_path)
    if is_return:
        return trimesh_object


def obj2trimesh_and_save_normalized(
    obj,
    path=None,
    idx="unknown",
    name=None,
    is_return=False,
    point_cloud=False,
    export_json=True,
):
    trimesh_object = obj2trimesh(obj)
    if idx == "unknown":
        idx = f"random_{np.random.randint(0, 10000)}"
    else:
        idx = str(idx)
    if path is None:
        path = os.path.join(os.path.curdir, "outputs")
    if not os.path.exists(path):
        os.mkdir(path)
    if not isinstance(path, Path):
        path = Path(path)
    (path / idx).mkdir(exist_ok=True)
    (path / idx / "objs").mkdir(exist_ok=True)
    # (path / idx / "point_cloud").mkdir(exist_ok=True)
    # File path for saving the .obj file
    file_path = os.path.join(path, idx, f"{obj.name}_part_{int(idx)+1}.obj")
    # normalize trimesh
    # Get the current bounds of the mesh
    bounds = trimesh_object.bounds

    # Calculate the range of the current bounds
    x_range = bounds[1][0] - bounds[0][0]
    y_range = bounds[1][1] - bounds[0][1]
    z_range = bounds[1][2] - bounds[0][2]

    # Calculate the scale factor to fit the mesh within [-1, 1]
    scale_factor = 1.0 / max(x_range, y_range, z_range)

    # Scale the mesh
    trimesh_object.vertices *= 2 * scale_factor

    # Translate the mesh to center it around the origin
    trimesh_object.vertices -= [
        scale_factor * (bounds[0][i] + bounds[1][i]) for i in range(3)
    ]

    # Now the vertices should be within the range [-1, 1]
    trimesh_object.export(file_path)

    # if point_cloud:
    #     pc_path = os.path.join(path, idx, f"{idx}.npz")
    # sample_and_save_points(torch.tensor(trimesh_object.vertices, dtype=torch.float32), torch.tensor(trimesh_object.faces), pc_path)

    if is_return:
        return trimesh_object


def new_cube(**kwargs):
    kwargs["location"] = kwargs.get("location", (0, 0, 0))
    bpy.ops.mesh.primitive_cube_add(**kwargs)
    return bpy.context.active_object


def new_bbox(x, x_, y, y_, z, z_):
    obj = new_cube()
    obj.location = (x + x_) / 2, (y + y_) / 2, (z + z_) / 2
    obj.scale = (x_ - x) / 2, (y_ - y) / 2, (z_ - z) / 2
    butil.apply_transform(obj, True)
    return obj


def new_bbox_2d(x, x_, y, y_, z=0):
    obj = new_plane()
    obj.location = (x + x_) / 2, (y + y_) / 2, z
    obj.scale = (x_ - x) / 2, (y_ - y) / 2, 1
    butil.apply_transform(obj, True)
    return obj


def new_icosphere(**kwargs):
    kwargs["location"] = kwargs.get("location", (0, 0, 0))
    bpy.ops.mesh.primitive_ico_sphere_add(**kwargs)
    return bpy.context.active_object


def new_circle(**kwargs):
    kwargs["location"] = kwargs.get("location", (1, 0, 0))
    bpy.ops.mesh.primitive_circle_add(**kwargs)
    obj = bpy.context.active_object
    butil.apply_transform(obj, loc=True)
    return obj


def new_base_circle(**kwargs):
    kwargs["location"] = kwargs.get("location", (0, 0, 0))
    bpy.ops.mesh.primitive_circle_add(**kwargs)
    obj = bpy.context.active_object
    return obj


def new_empty(**kwargs):
    kwargs["location"] = kwargs.get("location", (0, 0, 0))
    bpy.ops.object.empty_add(**kwargs)
    obj = bpy.context.active_object
    obj.scale = kwargs.get("scale", (1, 1, 1))
    return obj


def new_plane(**kwargs):
    kwargs["location"] = kwargs.get("location", (0, 0, 0))
    bpy.ops.mesh.primitive_plane_add(**kwargs)
    obj = bpy.context.active_object
    butil.apply_transform(obj, loc=True)
    return obj


def new_cylinder(**kwargs):
    kwargs["location"] = kwargs.get("location", (0, 0, 0.5))
    kwargs["depth"] = kwargs.get("depth", 1)
    bpy.ops.mesh.primitive_cylinder_add(**kwargs)
    obj = bpy.context.active_object
    butil.apply_transform(obj, loc=True)
    return obj


def new_base_cylinder(**kwargs):
    bpy.ops.mesh.primitive_cylinder_add(**kwargs)
    obj = bpy.context.active_object
    butil.apply_transform(obj, loc=True)
    return obj


def new_grid(**kwargs):
    kwargs["location"] = kwargs.get("location", (0, 0, 0))
    bpy.ops.mesh.primitive_grid_add(**kwargs)
    obj = bpy.context.active_object
    butil.apply_transform(obj, loc=True)
    return obj


def new_line(subdivisions=1, scale=1.0):
    vertices = np.stack(
        [
            np.linspace(0, scale, subdivisions + 1),
            np.zeros(subdivisions + 1),
            np.zeros(subdivisions + 1),
        ],
        -1,
    )
    edges = np.stack([np.arange(subdivisions), np.arange(1, subdivisions + 1)], -1)
    obj = mesh2obj(data2mesh(vertices, edges))
    return obj


def join_objects(obj):
    butil.select_none()
    if not isinstance(obj, list):
        obj = [obj]
    if len(obj) == 1:
        return obj[0]
    bpy.context.view_layer.objects.active = obj[0]
    butil.select_none()
    butil.select(obj)
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.location = 0, 0, 0
    obj.rotation_euler = 0, 0, 0
    obj.scale = 1, 1, 1
    butil.select_none()
    return obj


def add_joint(parent, child, joint_info):
    robot_tree[child] = (parent, joint_info)


def join_objects_save_whole(obj, path=None, idx="unknown", name=None, join=True, use_bpy=False):
    butil.select_none()
    if not isinstance(obj, list):
        obj = [obj]
    bpy.context.view_layer.objects.active = obj[0]
    butil.select_none()
    butil.select(obj)
    if join:
        bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.location = 0, 0, 0
    obj.rotation_euler = 0, 0, 0
    obj.scale = 1, 1, 1
    save_whole_object_normalized(obj, path, idx, use_bpy=use_bpy)
    butil.select_none()
    return obj


def save_parts_join_objects(obj, path=None, idx="unknown", name=None):
    butil.select_none()
    if not isinstance(obj, list):
        obj = [obj]
    if name is None:
        name = "unknown"
    if not isinstance(name, list):
        name = [name] * len(obj)
    if len(obj) == 1:
        return obj[0]
    # The original render engine and world node_tree should be memorized
    original_render_engine = bpy.context.scene.render.engine
    original_node_tree = bpy.context.scene.world.node_tree
    #Save a reference to the original scene
    original_scene = bpy.context.scene
    save_parts(obj, path, idx, name)
    # We need to link all these objects into view_layer
    view_layer = bpy.context.view_layer
    for part in obj:
        if part.name not in view_layer.objects:
            view_layer.active_layer_collection.collection.objects.link(part)
    bpy.context.scene.render.engine = original_render_engine
    # Now switch back to the original scene
    bpy.context.window.scene = original_scene
    bpy.context.view_layer.objects.active = obj[0]
    butil.select_none()
    butil.select(obj)
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.location = 0, 0, 0
    obj.rotation_euler = 0, 0, 0
    obj.scale = 1, 1, 1
    butil.select_none()
    return obj


def save_parts(objects, path=None, idx="unknown", name=None):
    assert len(objects) == len(name)
    if idx == "unknown":
        idx = f"random_{np.random.randint(0, 10000)}"
    else:
        idx = str(idx)
    if path is None:
        path = os.path.join(os.path.curdir, "outputs")
    if not os.path.exists(path):
        os.makedirs(path)
    if not isinstance(path, Path):
        path = Path(path)
    (path / (idx)).mkdir(exist_ok=True)
    butil.select_none()
    for i, part in enumerate(objects):
        # Reference the current view layer
        view_layer = bpy.context.view_layer
        # Link the object to the active view layer's collection
        if part.name not in view_layer.objects:
            view_layer.active_layer_collection.collection.objects.link(part)
        bpy.ops.object.select_all(action="DESELECT")
        # Select the current object
        part.select_set(True)
        # Create a new scene
        new_scene = bpy.data.scenes.new(f"Scene_for_{part.name}")
        # Link the object to the new scene
        new_scene.collection.objects.link(part)
        # Make the new scene active
        bpy.context.window.scene = new_scene
        # File path for saving the .blend file
        if name:
            file_path = os.path.join(
                path, "parts_seed_" + idx, f"{name[i]}_part_{i+1}.blend"
            )
        else:
            file_path = os.path.join(
                path, "parts_seed_" + idx, f"{part.name}_part_{i+1}.blend"
            )
        # Save the current scene as a new .blend file
        bpy.ops.wm.save_as_mainfile(filepath=file_path)
    butil.select_none()


def save_whole_object(object, path=None, idx="unknown"):
    if idx == "unknown":
        idx = f"random_{np.random.randint(0, 10000)}"
    else:
        idx = str(idx)
    if path is None:
        path = os.path.join(os.path.curdir, "outputs")
    if not os.path.exists(path):
        os.makedirs(path)
    if not isinstance(path, Path):
        path = Path(path)
    (path / (idx)).mkdir(exist_ok=True)
    butil.select_none()
    # # Reference the current view layer
    # view_layer = bpy.context.view_layer
    # # Link the object to the active view layer's collection
    # if object.name not in view_layer.objects:
    #     view_layer.active_layer_collection.collection.objects.link(object)
    # bpy.ops.object.select_all(action="DESELECT")
    # Select the current object
    object.select_set(True)
    # # Create a new scene
    # new_scene = bpy.data.scenes.new(f"Scene_for_{object.name}")
    # # Link the object to the new scene
    # new_scene.collection.objects.link(object)
    # # Make the new scene active
    # bpy.context.window.scene = new_scene
    # # File path for saving the .blend file
    file_path = os.path.join(path, idx, "objs/whole.obj")
    # Save the current scene as a new .obj file
    trimesh_object = obj2trimesh(object)
    trimesh_object.export(file_path)
    # Save the current scene as a new .blend file
    # bpy.ops.wm.save_as_mainfile(filepath=file_path)
    butil.select_none()

import random

def get_translation_matrix(x, y, z):
    matrix = np.array([
        [1, 0, 0, x],
        [0, 1, 0, y],
        [0, 0, 1, z],
        [0, 0, 0, 1]
    ])
    return matrix

def save_whole_object_normalized(object, path=None, idx="unknown", name=None, use_bpy=False):
    global robot_tree, root
    if idx == "unknown":
        idx = f"random_{np.random.randint(0, 10000)}"
    else:
        idx = str(idx)
    if path is None:
        path = os.path.join(os.path.curdir, "outputs")
    if not os.path.exists(path):
        os.makedirs(path)
    if not isinstance(path, Path):
        path = Path(path)
    (path / (idx)).mkdir(exist_ok=True)
    (path / (idx) / "objs").mkdir(exist_ok=True)
    # (path / (idx) / "point_cloud").mkdir(exist_ok=True)
    json_path = os.path.join(path, f"data_infos_{idx}.json")
    if not os.path.exists(json_path):
        infos = []
    else:
        with open(json_path, "r") as f:
            infos = json.load(f)

    if infos:
        info_case = infos[-1]
    else:
        info_case = {}

    if "id" not in info_case.keys():
        info_case["id"] = idx
    obj_name = os.path.basename(path)[:-7]
    info_case["obj_name"] = obj_name
    # info_case["category"] = category
    info_case["file_obj_path"] = os.path.join(path, f"{idx}/objs/whole.obj")
    butil.select_none()
    # # Reference the current view layer
    # view_layer = bpy.context.view_layer
    # # Link the object to the active view layer's collection
    # if object.name not in view_layer.objects:
    #     view_layer.active_layer_collection.collection.objects.link(object)
    # bpy.ops.object.select_all(action="DESELECT")
    # Select the current object
    object.select_set(True)
    # # Create a new scene
    # new_scene = bpy.data.scenes.new(f"Scene_for_{object.name}")
    # # Link the object to the new scene
    # new_scene.collection.objects.link(object)
    # # Make the new scene active
    # bpy.context.window.scene = new_scene
    # # File path for saving the .blend file
    file_path = os.path.join(path, idx, "objs", "whole.obj")
    # Save the current scene as a new .obj file
    trimesh_object = obj2trimesh(object)
    # normalize trimesh
    # Get the current bounds of the mesh
    bounds = trimesh_object.bounds.copy()

    # Calculate the range of the current bounds
    x_range = bounds[1][0] - bounds[0][0]
    y_range = bounds[1][1] - bounds[0][1]
    z_range = bounds[1][2] - bounds[0][2]

    # Calculate the scale factor to fit the mesh within [-1, 1]
    scale_factor = 1.0 / max(x_range, y_range, z_range)

    # Translate the mesh to center it around the origin
    trimesh_object.vertices -= [
        (bounds[0][j] + bounds[1][j]) / 2 for j in range(3)
    ]

    # Scale the mesh
    trimesh_object.vertices *= scale_factor

    angle_degrees = 90  # 45 degrees
    angle_radians = -np.radians(angle_degrees)

    # # Create a rotation matrix for the x-axis
    # # For a clockwise rotation when viewed from the positive x-axis,
    # # we use a positive angle with np.cos and a negative angle with np.sin
    rotation_matrix = np.array(
        [
            [1, 0, 0],
            [0, np.cos(angle_radians), -np.sin(angle_radians)],
            [0, np.sin(angle_radians), np.cos(angle_radians)],
        ]
    )

    # # Apply the rotation matrix to the vertices
    rotated_vertices = np.dot(trimesh_object.vertices, rotation_matrix.T)

    # Create a new Trimesh object with the rotated vertices
    trimesh_object = trimesh.Trimesh(
        vertices=rotated_vertices, faces=trimesh_object.faces
    )

    trimesh_object.export(file_path)

    # sample point clouds
    # sample_and_save_points(torch.tensor(trimesh_object.vertices, dtype=torch.float32), torch.tensor(trimesh_object.faces), os.path.join(path, f"{idx}/point_cloud/whole"))
    path_list = glob.glob(os.path.join(path, idx, "objs", "*.obj"))
    path_list.remove(file_path)

    x_min, y_min, z_min, x_max, y_max, z_max = 300, 300, 300, -300, -300, -300
    origins = {}
    for obj_path in path_list:
        mesh = trimesh.load_mesh(obj_path)
        bs = mesh.bounds
        index = int(str(obj_path).split('/')[-1].split('.')[0])
        origins[index] = ((bs[0][0] + bs[1][0]) / 2, (bs[0][1] + bs[1][1]) / 2, (bs[0][2] + bs[1][2]) / 2)
        x_min, y_min, z_min, x_max, y_max, z_max = min(x_min, bs[0][0]), min(y_min, bs[0][1]), min(z_min, bs[0][2]), max(x_max, bs[1][0]), max(y_max, bs[1][1]), max(z_max, bs[1][2])
        mesh.vertices -= [origins[index][0], origins[index][1], origins[index][2]]
        mesh = trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces)
        mesh.export(obj_path)

    # for obj_path in path_list:
    #     mesh = trimesh.load_mesh(obj_path)
    #
    #     # Translate the mesh to center it around the origin
    #     mesh.vertices -= [
    #         (x_min + x_max) / 2, (y_min + y_max) / 2, (z_min + z_max) / 2
    #     ]
    #
    #     mesh.vertices *= scale_factor
    #
    #     rotated_vertices = np.dot(mesh.vertices, rotation_matrix.T)
    #
    #     # Apply the rotation matrix to the vertices
    #
    #
    #     # Create a new Trimesh object with the rotated vertices
    #     if use_bpy:
    #         mesh = trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces)
    #     else:
    #         mesh = trimesh.Trimesh(rotated_vertices, faces=mesh.faces)
    #
    #     mesh.export(obj_path)
    #
    #     base_filename = os.path.basename(obj_path)
    #     n = base_filename.split(".")[0]

        # sample points
        # sample_and_save_points(torch.tensor(mesh.vertices, dtype=torch.float32), torch.tensor(mesh.faces), os.path.join(path, f"{idx}/point_cloud/{n}"))
    links = {}
    joints= []
    origins["world"] = (0, 0, 0)
    root = urdfpy.Link("world", visuals=None, collisions=None, inertial=None)
    links["world"] = root
    for link in robot_tree.keys():
        if link not in links.keys():
            mesh_idx = link
            if robot_tree[link][1].get("substitute_mesh_idx", None) is not None:
                mesh_idx = robot_tree[link][1]["substitute_mesh_idx"]
            l = urdfpy.Link(f'{link}', visuals=[urdfpy.Visual(geometry=urdfpy.Geometry(mesh=urdfpy.Mesh(filename=os.path.join(path, idx, "objs", f"{mesh_idx}.obj"))))], collisions=[urdfpy.Collision(name="temp", origin=None, geometry=urdfpy.Geometry(mesh=urdfpy.Mesh(filename=os.path.join(path, idx, "objs", f"{link}.obj"))))], inertial=None)
            links[link] = l
        else:
            l = links[link]
        joint_info = robot_tree[link][1]
        parent = robot_tree[link][0]
        # if parent is None:
        #     joint_root = urdfpy.Joint(f"joint_root_{random.randint(0, 10000000000000000000000000000000000000)}", "prismatic", "world", link, axis=(0, 0, 1), origin=None, limit=urdfpy.JointLimit(
        #         0, 1, -1, 1
        #     ))
        #     joints.append(joint_root)
        #     continue
        if link == root:
            continue
        if parent is None:
            parent = "world"
            pos = origins[link]
            joint_info = {
                "name": f"{random.randint(0, 10000000000000000000000000000000000000000)}_root",
                "type": "fixed",
                "origin": get_translation_matrix(pos[0], pos[1], pos[2])
            }
        if parent not in links.keys():
            mesh_idx = parent
            if robot_tree.get(parent, None) is not None and robot_tree[parent][1] is not None and robot_tree[parent][1].get("substitute_mesh_idx", None) is not None:
                mesh_idx = robot_tree[parent][1]["substitute_mesh_idx"]
            p = urdfpy.Link(f'{parent}', visuals=[urdfpy.Visual(geometry=urdfpy.Geometry(mesh=urdfpy.Mesh(filename=os.path.join(path, idx, "objs", f"{mesh_idx}.obj"))))], collisions=None, inertial=None)
            links[parent] = p
        else:
            p = links[parent]
        pos_l = origins[link]
        pos_p = origins[parent]
        origin_shift = (pos_l[0] - pos_p[0], pos_l[1] - pos_p[1], pos_l[2] - pos_p[2])
        limit_info = joint_info.get("limit", None)
        # if joint_info.get("type", "fixed") == "prismatic":
        #     if limit_info is not None and limit_info.get("lower", None) is not None:
        #         limit_info["lower"] *= scale_factor
        #         limit_info["upper"] *= scale_factor
        if limit_info:
            limit = urdfpy.JointLimit(limit_info.get("effort", 2000), limit_info.get("velocity", 2), limit_info.get("lower", -1), limit_info.get("upper", 1))
            if limit_info.get("lower_1"):
                limit_1 = urdfpy.JointLimit(limit_info.get("effort", 2000), limit_info.get("velocity", 2), limit_info.get("lower_1", -1), limit_info.get("upper_1", 1))
        else:
            limit = None
        type = joint_info.get("type", "fixed")
        if type == "fixed" or type == "prismatic":
            j = urdfpy.Joint(joint_info.get("name", "temp"), joint_info.get("type", "fixed"), parent, link,
                             axis=joint_info.get("axis", None),
                             origin=get_translation_matrix(origin_shift[0], origin_shift[1], origin_shift[2]),
                             limit=limit)
            joints.append(j)
        elif type == "revolute" or type == "continuous":
            shift_axis = joint_info.get("origin_shift", (0, 0, 0))
            l_abstract = urdfpy.Link(f'abstract_{parent}_{link}', visuals=None, collisions=None, inertial=None)
            links[f'abstract_{parent}_{link}'] = l_abstract
            j_real = urdfpy.Joint(joint_info.get("name"), joint_info.get("type", "fixed"), parent, f'abstract_{parent}_{link}', axis=joint_info.get("axis", None), limit=limit, origin=get_translation_matrix(origin_shift[0] + shift_axis[0], origin_shift[1] + shift_axis[1], origin_shift[2] + shift_axis[2]))
            j_abstract = urdfpy.Joint(str(random.randint(-10, 100000000000000000000000000000000000000)), "fixed", f"abstract_{parent}_{link}", link, axis=None, limit=None, origin=get_translation_matrix(-shift_axis[0], -shift_axis[1], -shift_axis[2]))
            joints.append(j_real)
            joints.append(j_abstract)
        elif type == "revolute_prismatic" or type == "continuous_prismatic":
            shift_axis = joint_info.get("origin_shift", (0, 0, 0))
            l_abstract = urdfpy.Link(f'abstract_{parent}_{link}', visuals=None, collisions=None, inertial=None)
            links[f'abstract_{parent}_{link}'] = l_abstract
            j_real = urdfpy.Joint(joint_info.get("name"), joint_info.get("type").split('_')[0], parent,
                                  f'abstract_{parent}_{link}', axis=joint_info.get("axis", None), limit=limit,
                                  origin=get_translation_matrix(origin_shift[0] + shift_axis[0],
                                                                origin_shift[1] + shift_axis[1],
                                                                origin_shift[2] + shift_axis[2]))
            j_abstract = urdfpy.Joint(str(random.randint(-10, 100000000000000000000000000000000000000)), "fixed",
                                      f"abstract_{parent}_{link}", link, axis=None, limit=None,
                                      origin=get_translation_matrix(-shift_axis[0], -shift_axis[1], -shift_axis[2]))
            joints.append(j_real)
            joints.append(j_abstract)
            joint_prismatic = urdfpy.Joint(f"joint_prismatic_{random.randint(0, 1000000000000000000000000000)}",
                                           "prismatic", parent, link, axis=joint_info.get("axis_1", None), limit=limit_1, origin=get_translation_matrix(origin_shift[0], origin_shift[1], origin_shift[2]))
            joints.append(joint_prismatic)

    robot = urdfpy.URDF("scene", list(links.values()), joints=joints)
    robot.save(os.path.join(path, idx, "scene.urdf"))
    #robot.show()
    robot_tree = {}
    butil.select_none()


def save_obj_parts_join_objects(
    obj, path=None, idx="unknown", name=None, obj_name=None, first=True
):
    butil.select_none()
    if not isinstance(obj, list):
        obj = [obj]
    if name is None:
        name = "unknown"
    if not isinstance(name, list):
        name = [name] * len(obj)
    if len(obj) == 1:
        return obj[0]
    # The original render engine and world node_tree should be memorized
    # original_render_engine = bpy.context.scene.render.engine
    # original_node_tree = bpy.context.scene.world.node_tree
    # Save a reference to the original scene
    original_scene = bpy.context.scene
    save_parts_export_obj_normalized_json(obj, path, idx, name, obj_name, first)
    # We need to link all these objects into view_layer
    view_layer = bpy.context.view_layer
    for part in obj:
        if part.name not in view_layer.objects:
            view_layer.active_layer_collection.collection.objects.link(part)
    # bpy.context.scene.render.engine = original_render_engine
    # Now switch back to the original scene
    bpy.context.window.scene = original_scene
    bpy.context.view_layer.objects.active = obj[0]
    butil.select_none()
    butil.select(obj)
    bpy.ops.object.join()
    obj = bpy.context.active_object
    obj.location = 0, 0, 0
    obj.rotation_euler = 0, 0, 0
    obj.scale = 1, 1, 1
    save_whole_object_normalized(obj, path, idx)
    butil.select_none()
    return obj


def save_obj_parts_add(
    obj, path=None, idx="unknown", name=None, obj_name=None, first=True, use_bpy=False, parent_obj_id=None, joint_info=None
):
    butil.select_none()
    if not isinstance(obj, list):
        obj = [obj]
    if name is None:
        name = "unknown"
    if not isinstance(name, list):
        name = [name] * len(obj)
    # The original render engine and world node_tree should be memorized
    # original_render_engine = bpy.context.scene.render.engine
    # original_node_tree = bpy.context.scene.world.node_tree
    # Save a reference to the original scene
    original_scene = bpy.context.scene
    saved = save_part_export_obj_normalized_add_json(obj, path, idx, name, first=first, use_bpy=use_bpy, parent_obj_id=parent_obj_id, joint_info=joint_info)
    # We need to link all these objects into view_layer
    view_layer = bpy.context.view_layer
    for part in obj:
        if part.name not in view_layer.objects:
            view_layer.active_layer_collection.collection.objects.link(part)
    # bpy.context.scene.render.engine = original_render_engine
    # Now switch back to the original scene
    bpy.context.window.scene = original_scene
    bpy.context.view_layer.objects.active = obj[0]
    butil.select_none()
    return saved


def save_parts_export_obj(
    parts, path=None, idx="unknown", name=None, obj_name=None, first=True
):
    assert len(parts) == len(name)
    if idx == "unknown":
        idx = f"random_{np.random.randint(0, 10000)}"
    else:
        idx = str(idx)
    if not isinstance(obj_name, str):
        obj_name = "unknown"
    if path is None:
        path = os.path.join(os.path.curdir, "outputs")
    if not os.path.exists(path):
        os.makedirs(path)
    if not isinstance(path, Path):
        path = Path(path)
    (path / (idx)).mkdir(exist_ok=True)
    (path / (idx) / "objs").mkdir(exist_ok=True)
    # (path / (idx) / "point_cloud").mkdir(exist_ok=True)
    butil.select_none()

    json_path = os.path.join(path, f"data_infos_{idx}.json")
    if not os.path.exists(json_path):
        infos = []
    else:
        with open(json_path, "r") as f:
            infos = json.load(f)

    if infos and not first:
        info_case = infos[-1]
    else:
        info_case = {}

    info_case["id"] = idx

    info_case["obj_name"] = obj_name
    # info_case["category"] = category
    info_case["file_obj_path"] = os.path.join(path, f"{idx}/objs/whole.obj")
    # info_case["file_pcd_path"] = os.path.join(path, f"{idx}/point_cloud/whole.npz")
    info_parts = info_case.get("part", [])
    length = len(info_parts)
    for i, part in enumerate(parts):
        # Reference the current view layer
        view_layer = bpy.context.view_layer
        # Link the object to the active view layer's collection
        if part.name not in view_layer.objects:
            view_layer.active_layer_collection.collection.objects.link(part)
        bpy.ops.object.select_all(action="DESELECT")

        # Select the current object
        part.select_set(True)
        # Create a new scene
        #new_scene = bpy.data.scenes.new(f"Scene_for_{part.name}")
        # Link the object to the new scene
        #new_scene.collection.objects.link(part)
        # Make the new scene active
        #bpy.context.window.scene = new_scene
        # File path for saving the .blend file
        file_path = os.path.join(path, idx, f"objs/{str(i+length)}.obj")
        # Save the current scene as a new .obj file
        trimesh_object = obj2trimesh(part)
        trimesh_object.export(file_path)

        # write json here
        part_info = {}
        part_info["part_name"] = name[i] + "_part"
        part_info["file_name"] = str(i + length) + ".obj"
        part_info["file_obj_path"] = os.path.join(
            path, f"{idx}/objs/{str(i+length)}.obj"
        )
        # pcd_path = os.path.join(path, f"{idx}/point_cloud/{str(i+length)}")
        # part_info["file_pcd_path"] = pcd_path + ".npz"
        info_parts.append(part_info)

    info_case["part"] = info_parts
    if first:
        infos.append(info_case)
    with open(json_path, "w") as f:
        json.dump(infos, f, indent=2)

    butil.select_none()


def save_parts_export_obj_normalized_json(
    parts, path=None, idx="unknown", name=None, obj_name=None, first=True
):
    assert len(parts) == len(name)
    if idx == "unknown":
        idx = f"random_{np.random.randint(0, 10000)}"
    else:
        idx = str(idx)
    if isinstance(obj_name, str):
        obj_name = str(obj_name)
    if path is None:
        path = os.path.join(os.path.curdir, "outputs")
    if not os.path.exists(path):
        os.makedirs(path)
    if not isinstance(path, Path):
        path = Path(path)
    (path / idx).mkdir(exist_ok=True)
    (path / idx / "objs").mkdir(exist_ok=True)
    # (path / idx / "point_cloud").mkdir(exist_ok=True)
    butil.select_none()

    json_path = os.path.join(path, f"data_infos_{idx}.json")
    if not os.path.exists(json_path):
        infos = []
    else:
        with open(json_path, "r") as f:
            infos = json.load(f)

    if infos and not first:
        info_case = infos[-1]
    else:
        info_case = {}
    info_case["id"] = idx

    info_case["obj_name"] = obj_name
    # info_case["category"] = category
    info_case["file_obj_path"] = os.path.join(path, f"{idx}/objs/whole.obj")
    # info_case["file_pcd_path"] = os.path.join(path, f"{idx}/point_cloud/whole.npz")
    info_parts = info_case.get("part", [])
    length = len(info_parts)
    for i, part in enumerate(parts):
        # Reference the current view layer
        view_layer = bpy.context.view_layer
        # Link the object to the active view layer's collection
        if part.name not in view_layer.objects:
            view_layer.active_layer_collection.collection.objects.link(part)
        bpy.ops.object.select_all(action="DESELECT")
        # Select the current object
        part.select_set(True)
        # Create a new scene
        new_scene = bpy.data.scenes.new(f"Scene_for_{part.name}")
        # Link the object to the new scene
        new_scene.collection.objects.link(part)
        # Make the new scene active
        bpy.context.window.scene = new_scene
        # File path for saving the .blend file
        file_path = os.path.join(path, idx, f"objs/{i+length}.obj")

        # Save the current scene as a new .obj file
        trimesh_object = obj2trimesh(part)
        trimesh_object.export(file_path)

        # write json here
        part_info = {}
        part_info["part_name"] = name[i] + "_part"
        part_info["file_name"] = str(i + length) + ".obj"
        part_info["file_obj_path"] = os.path.join(
            path, f"{idx}/objs/{str(i+length)}.obj"
        )
        # pcd_path = os.path.join(path, f"{idx}/point_cloud/{str(i+length)}")
        # part_info["file_pcd_path"] = pcd_path + ".npz"
        info_parts.append(part_info)

    info_case["part"] = info_parts
    if first:
        infos.append(info_case)
    with open(json_path, "w") as f:
        json.dump(infos, f, indent=2)

    butil.select_none()


def save_part_export_obj_normalized_add_json(
    parts, path=None, idx="unknown", name=None, use_bpy=False, first=True, parent_obj_id=None, joint_info=None
):
    global robot_tree, root
    assert len(parts) == len(name)
    if idx == "unknown":
        idx = f"random_{np.random.randint(0, 10000)}"
    else:
        idx = str(idx)
    if path is None:
        path = os.path.join(os.path.curdir, "outputs")
    if not os.path.exists(path):
        os.makedirs(path)
    if not isinstance(path, Path):
        path = Path(path)
    (path / idx).mkdir(exist_ok=True)
    (path / idx / "objs").mkdir(exist_ok=True)
    # (path / idx / "point_cloud").mkdir(exist_ok=True)
    butil.select_none()

    json_path = os.path.join(path, f"data_infos_{idx}.json")
    if not os.path.exists(json_path):
        infos = []
        first = True
    else:
        with open(json_path, "r") as f:
            infos = json.load(f)

    if infos and not first:
        info_case = infos[-1]
    else:
        info_case = {}

    # info_parts = info_case["part"]
    info_parts = info_case.get("part", [])
    length = len(info_parts)
    saved = []
    for i, part in enumerate(parts):
        # Reference the current view layer
        view_layer = bpy.context.view_layer
        # if not part.name in bpy.context.collection.objects.keys():
            # bpy.context.collection.objects.link(part)
        # Link the object to the active view layer's collection
        if part.name not in view_layer.objects:
            view_layer.active_layer_collection.collection.objects.link(part)
        # butil.select_none()
        # bpy.context.view_layer.objects.active = part  # Set the object as active
        bpy.ops.object.select_all(action="DESELECT")
        # Select the current object
        part.select_set(True)
        # Create a new scene
        # new_scene = bpy.data.scenes.new(f"Scene_for_{part.name}")
        # Link the object to the new scene
        # new_scene.collection.objects.link(part)
        # Make the new scene active
        # bpy.context.window.scene = new_scene
        # File path for saving the .blend file
        file_path = os.path.join(path, idx, f"objs/{i + length}.obj")
        robot_tree[i + length] = [parent_obj_id, joint_info]
        if parent_obj_id is not None and root is None:
            root = i + length
        saved.append(i + length)
        if use_bpy:
            bpy.ops.export_scene.obj(filepath=file_path, use_selection=True)
            os.remove(os.path.join(path, idx, f"objs/{i + length}.mtl"))

        # Save the current scene as a new .obj file
        else:
            trimesh_object = obj2trimesh(part)
            trimesh_object.export(file_path)
        part.select_set(False)

        # write json here
        part_info = {}
        part_info["part_name"] = name[i] + "_part"
        part_info["file_name"] = str(i + length) + ".obj"
        part_info["file_obj_path"] = os.path.join(
            path, f"{idx}/objs/{str(i + length)}.obj"
        )
        # pcd_path = os.path.join(path, f"{idx}/point_cloud/{str(i + length)}")
        # part_info["file_pcd_path"] = pcd_path + ".npz"
        info_parts.append(part_info)

    info_case["part"] = info_parts
    if first:
        infos.append(info_case)
        print(infos)
    with open(json_path, "w") as f:
        json.dump(infos, f, indent=2)

    butil.select_none()
    return saved


def save_objects(obj, path=None, idx="unknown", name=None):
    butil.select_none()
    if not isinstance(obj, list):
        obj = [obj]
    if name is not None and not isinstance(name, list):
        name = [name] * len(obj)
    if len(obj) == 1:
        return obj[0]
    # The original render engine and world node_tree should be memorized
    # original_render_engine = bpy.context.scene.render.engine
    # original_node_tree = bpy.context.scene.world.node_tree
    # Save a reference to the original scene
    original_scene = bpy.context.scene
    save_parts(obj, path, idx, name)
    # We need to link all these objects into view_layer
    view_layer = bpy.context.view_layer
    for part in obj:
        if part.name not in view_layer.objects:
            view_layer.active_layer_collection.collection.objects.link(part)
    # bpy.context.scene.render.engine = original_render_engine
    # Now switch back to the original scene
    bpy.context.window.scene = original_scene
    bpy.context.view_layer.objects.active = obj[0]
    butil.select_none()
    # return obj


def save_objects_obj(
    obj, path=None, idx="unknown", name=None, obj_name=None, first=True
):
    butil.select_none()
    if not isinstance(obj, list):
        obj = [obj]
    if name is not None and not isinstance(name, list):
        name = [name] * len(obj)
    # The original render engine and world node_tree should be memorized
    # original_render_engine = bpy.context.scene.render.engine
    # original_node_tree = bpy.context.scene.world.node_tree
    # Save a reference to the original scene
    original_scene = bpy.context.scene
    save_parts_export_obj(obj, path, idx, name, obj_name, first)
    # We need to link all these objects into view_layer
    view_layer = bpy.context.view_layer
    for part in obj:
        if part.name not in view_layer.objects:
            view_layer.active_layer_collection.collection.objects.link(part)
    # bpy.context.scene.render.engine = original_render_engine
    # Now switch back to the original scene
    bpy.context.window.scene = original_scene
    bpy.context.view_layer.objects.active = obj[0]
    butil.select_none()
    # return obj


def save_file_path(path=None, name=None, idx=None, i=999):
    if idx == "unknown":
        idx = f"random_{np.random.randint(0, 10000)}"
    else:
        idx = str(idx)
    if path is None:
        path = os.path.join(os.path.curdir, "outputs")
    if not os.path.exists(path):
        os.mkdir(path)
    if not isinstance(path, Path):
        path = Path(path)
    (path / ("parts_seed_" + idx)).mkdir(exist_ok=True)
    save_path = os.path.join(path, f"parts_seed_{idx}", f"{name}_{i}.blend")
    if os.path.exists(save_path):
        before_path = os.path.join(path, f"parts_seed_{idx}_before")
        if not os.path.exists(before_path):
            os.mkdir(before_path)
        os.rename(
            save_path,
            os.path.join(
                before_path,
                f"{name}_{i}_before_random_{np.random.randint(0, 10000)}.blend",
            ),
        )
    return save_path


def save_file_path_obj(path=None, name=None, idx=None, i=999):
    if idx == "unknown":
        idx = f"random_{np.random.randint(0, 10000)}"
    else:
        idx = str(idx)
    if path is None:
        path = os.path.join(os.path.curdir, "outputs")
    if not os.path.exists(path):
        os.mkdir(path)
    if not isinstance(path, Path):
        path = Path(path)
    (path / idx).mkdir(exist_ok=True)
    save_path = os.path.join(path, f"{idx}", f"{i}.obj")
    if os.path.exists(save_path):
        before_path = os.path.join(path, f"{idx}_before")
        if not os.path.exists(before_path):
            os.mkdir(before_path)
        os.rename(
            save_path,
            os.path.join(
                before_path,
                f"{name}_{i}_before_random_{np.random.randint(0, 10000)}.obj",
            ),
        )
    return save_path


def separate_loose(obj):
    select_none()
    objs = butil.split_object(obj)
    i = np.argmax([len(o.data.vertices) for o in objs])
    obj = objs[i]
    objs.remove(obj)
    butil.delete(objs)
    return obj


def print3d_clean_up(obj):
    bpy.ops.preferences.addon_enable(module="object_print3d_utils")
    with butil.ViewportMode(obj, "EDIT"), butil.Suppress():
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.quads_convert_to_tris(quad_method="BEAUTY", ngon_method="BEAUTY")
        bpy.ops.mesh.fill_holes()
        bpy.ops.mesh.quads_convert_to_tris(quad_method="BEAUTY", ngon_method="BEAUTY")
        bpy.ops.mesh.normals_make_consistent()
        bpy.ops.mesh.print3d_clean_distorted()
        bpy.ops.mesh.print3d_clean_non_manifold()
