# Copyright (C) 2024, Princeton University.
# This source code is licensed under the BSD 3-Clause license found in the LICENSE file in the root directory of this source tree.

# Authors: Hongyu Wen


import numpy as np
from numpy.random import normal as N
from numpy.random import randint as RI
from numpy.random import uniform as U

from infinigen.assets.material_assignments import AssetList
from infinigen.assets.utils.decorate import read_co
from infinigen.core import surface
from infinigen.core.nodes import node_utils
from infinigen.core.nodes.node_wrangler import Nodes, NodeWrangler
from infinigen.core.placement.factory import AssetFactory
from infinigen.core.util import blender as butil
from infinigen.core.util.bevelling import (
    add_bevel,
    complete_bevel,
    complete_no_bevel,
    get_bevel_edges,
)
from infinigen.core.util.blender import delete
from infinigen.core.util.math import FixedSeed
from infinigen.assets.utils.auxiliary_parts import random_auxiliary

from infinigen.assets.utils.object import (
    add_joint,
    data2mesh,
    join_objects,
    join_objects_save_whole,
    mesh2obj,
    new_bbox,
    new_cube,
    new_plane,
    save_obj_parts_join_objects,
    save_objects_obj,
    save_obj_parts_add,
    get_joint_name,
    add_internal_bbox,
    save_obj_parts_add
)

from numpy.random import choice




class DishwasherFactory(AssetFactory):
    def __init__(self, factory_seed, coarse=False, dimensions=[1.0, 1.0, 1.0]):
        super(DishwasherFactory, self).__init__(factory_seed, coarse=coarse)

        self.dimensions = dimensions
        with FixedSeed(factory_seed):
            self.params = self.sample_parameters(dimensions)
            self.ps, self.material_params, self.scratch, self.edge_wear = (
                self.get_material_params()
            )
        self.params.update(self.material_params)
        self.aux_divider = random_auxiliary("strainer")
        self.aux_handle = random_auxiliary("handles")
        self.use_aux_divider = choice([True, False], p=[0.8, 0.2])
        self.use_aux_handle = choice([True, False], p=[0.8, 0.2])
        self.control_on_door = choice([True, False], p=[0.5, 0.5])

    def get_material_params(self):
        material_assignments = AssetList["DishwasherFactory"]()
        params = {
            "Surface": material_assignments["surface"].assign_material(),
            "Front": material_assignments["front"].assign_material(),
            "WhiteMetal": material_assignments["white_metal"].assign_material(),
            "Top": material_assignments["top"].assign_material(),
            "NameMaterial": material_assignments["name_material"].assign_material(),
        }
        wrapped_params = {
            k: surface.shaderfunc_to_material(v) for k, v in params.items()
        }

        scratch_prob, edge_wear_prob = material_assignments["wear_tear_prob"]
        scratch, edge_wear = material_assignments["wear_tear"]

        is_scratch = np.random.uniform() < scratch_prob
        is_edge_wear = np.random.uniform() < edge_wear_prob
        if not is_scratch:
            scratch = None

        if not is_edge_wear:
            edge_wear = None

        return params, wrapped_params, scratch, edge_wear

    @staticmethod
    def sample_parameters(dimensions):
        # depth, width, height = dimensions
        depth = 1 + N(0, 0.1)
        width = 1 + N(0, 0.1)
        height = 1 + N(0, 0.1)
        door_thickness = U(0.05, 0.1) * depth
        door_rotation = 0  # Set to 0 for now

        rack_radius = U(0.01, 0.02) * depth
        rack_h_amount = RI(1, 4)
        brand_name = "BrandName"

        params = {
            "Depth": depth,
            "Width": width,
            "Height": height,
            "DoorThickness": door_thickness,
            "DoorRotation": door_rotation,
            "RackRadius": rack_radius,
            "RackAmount": rack_h_amount,
            "BrandName": brand_name,
        }
        return params

    def create_asset(self, **params):
        number_per_rack = [RI(1, 4) for i in range(self.params['RackAmount'])]
        self.number_per_rack = number_per_rack
        obj = butil.spawn_cube()
        butil.modify_mesh(
            obj,
            "NODES",
            node_group=nodegroup_dishwasher_geometry(preprocess=True),
            ng_inputs=self.params,
            apply=True,
        )
        bevel_edges = get_bevel_edges(obj)
        delete(obj)
        obj = butil.spawn_cube()
        butil.modify_mesh(
            obj,
            "NODES",
            node_group=nodegroup_dishwasher_geometry(),
            ng_inputs=self.params,
            apply=True,
        )
        obj = add_bevel(obj, bevel_edges, offset=0.01)
        #self.params.update(params)
        #self.params.update(self.ps)
        self.ps.update(params)
        return obj

    def finalize_assets(self, assets):
        if self.scratch:
            self.scratch.apply(assets)
        if self.edge_wear:
            self.edge_wear.apply(assets)
        first = True
        b_offset = np.random.uniform(0.01, self.params.get("DoorThickness") / 2)
        for i in range(4, 0, -1):
            joint_info = None
            parent_id = None
            if i == 1:
                body = butil.spawn_cube()
                butil.modify_mesh(
                    body,
                    "NODES",
                    node_group=nodegroup_dishwasher_geometry(preprocess=True, return_type_name="body"),
                    ng_inputs=self.params,
                    apply=True,
                )
                bevel_edges = get_bevel_edges(body)
                delete(body)
                body = butil.spawn_cube()
                butil.modify_mesh(
                    body,
                    "NODES",
                    node_group=nodegroup_dishwasher_geometry(return_type_name="body"),
                    ng_inputs=self.params,
                    apply=True,
                )
                body = add_bevel(body, bevel_edges, offset=b_offset, segments=32)
                save_obj_parts_add(body, self.ps.get("path"), self.ps.get("i"), "body", first=False, use_bpy=True, parent_obj_id=parent_id, joint_info=joint_info)
            elif i == 2:
                parent_id = "world"
                joint_info = {
                    "name": get_joint_name("revolute"),
                    "type": "revolute",
                    "axis": (0, 1, 0),
                    "limit": {
                        "lower": 0,
                        "upper": 3.14 * 0.5,
                    },
                    "origin_shift": (0, 0, -self.params.get("Height") / 2),
                }
                door = butil.spawn_cube()
                butil.modify_mesh(
                    door,
                    "NODES",
                    node_group=nodegroup_dishwasher_geometry(preprocess=True, return_type_name="door"),
                    ng_inputs=self.params,
                    apply=True,
                )
                bevel_edges = get_bevel_edges(door)
                delete(door)
                door = butil.spawn_cube()
                butil.modify_mesh(
                    door,
                    "NODES",
                    node_group=nodegroup_dishwasher_geometry(return_type_name="door"),
                    ng_inputs=self.params,
                    apply=True,
                )
                door = add_bevel(door, bevel_edges, offset=b_offset, segments=32)
                co_d = read_co(door)
                id_door = save_obj_parts_add(door, self.ps.get("path"), self.ps.get("i"), "door", first=False, use_bpy=True, parent_obj_id=parent_id, joint_info=joint_info)[0]
                z_max = co_h[:, 2].min()
                
            elif i == 3:
                parent_id = "world"
                joint_info = {
                    "name": get_joint_name("fixed"),
                    "type": "fixed",
                }
                handle = butil.spawn_cube()
                butil.modify_mesh(
                    handle,
                    "NODES",
                    node_group=nodegroup_dishwasher_geometry(return_type_name="handle"),
                    ng_inputs=self.params,
                    apply=True,
                )
                handle = add_bevel(handle, bevel_edges, offset=0.01)
                co = read_co(handle)
                if self.use_aux_handle:
                    handle_ = butil.deep_clone_obj(self.aux_handle[0])
                    handle_.rotation_euler = np.pi / 2, 0, np.pi / 2
                    butil.apply_transform(handle_)
                    handle_.scale = (co[:, 0].max() - co[:, 0].min(), co[:, 1].max() - co[:, 1].min(), co[:, 2].max() - co[:, 2].min())
                    butil.apply_transform(handle_)
                    handle_.location = (co[:, 0].max() + co[:, 0].min()) / 2, (co[:, 1].max() + co[:, 1].min()) / 2, (co[:, 2].max() + co[:, 2].min()) / 2
                    butil.apply_transform(handle_)
                    handle = handle_
                id_handle = save_obj_parts_add(handle, self.ps.get("path"), self.ps.get("i"), "handle", first=False, use_bpy=True, parent_obj_id=parent_id, joint_info=joint_info)[0]
                co_h = co
            else:
                heater = butil.spawn_cube()
                butil.modify_mesh(
                    heater,
                    "NODES",
                    node_group=nodegroup_dishwasher_geometry(preprocess=True, return_type_name="heater"),
                    ng_inputs=self.params,
                    apply=True,
                )
                bevel_edges = get_bevel_edges(heater)
                delete(heater)
                heater = butil.spawn_cube()
                butil.modify_mesh(
                    heater,
                    "NODES",
                    node_group=nodegroup_dishwasher_geometry(return_type_name="heater"),
                    ng_inputs=self.params,
                    apply=True,
                )
                heater = add_bevel(heater, bevel_edges, offset=b_offset, segments=32)
                save_obj_parts_add(heater, self.ps.get("path"), self.ps.get("i"), "heater", first=True, use_bpy=True, parent_obj_id=parent_id, joint_info=joint_info)
                
            # a = node_utils.save_geometry_new(
            #     assets,
            #     "part",
            #     i,
            #     self.params.get("i"),
            #     self.params.get("path"),
            #     first,
            #     True,
            #     False,
            #     material=material,
            #     parent_obj_id=parent_id,
            #     joint_info=joint_info
            # )
            # if a:
            #     first = False
        for i in range(1, self.params['RackAmount'] + 1):
            material = [self.ps.get("Surface"), self.scratch, self.edge_wear]
            parent_id = "world"
            joint_info = {
                "name": get_joint_name("prismatic"),
                "type": "prismatic",
                "axis": (1, 0, 0),
                "limit": {
                    "lower": 0,
                    "upper": self.params['Depth'] * 0.75,
                }
            }

            def store_bbox_and_substitute_mesh(obj, store_info):
                co = read_co(obj)
                obj.name = f"rack_{i}"
                h = co[:, 2].max()
                h_ = co[:, 2].min()
                l = co[:, 0].max()
                l_ = co[:, 0].min()
                w = co[:, 1].max()
                w_ = co[:, 1].min()
                store_info[obj.name] = (l, l_, w, w_, h, h_)
                if len(store_info) == 1:
                    pass
                else:
                    last_box = store_info[f"rack_{i - 1}"]
                    # last bbox is below current bbox
                    add_internal_bbox((l, l_, w, w_, h_, last_box[-2]))
                number = self.number_per_rack[i - 1]
                gap = (w - w_) * 0.05 / (number + 1)
                width = (w - w_) * 0.95 / number
                location = [(l + l_) / 2, gap + w_ + 0.5 * width, (h + h_) / 2]
                if self.use_aux_divider:
                    divider = butil.deep_clone_obj(self.aux_divider[0])
                    divider.rotation_euler = np.pi / 2, 0, np.pi / 2
                    butil.apply_transform(divider)
                    scale = [l - l_, w - w_, h - h_]
                    scale[1] *= 0.95 / number
                    divider.scale = scale
                    butil.apply_transform(divider)
                    #divider.location = (l + l_) / 2, gap + w_ + 0.5 * width, (h + h_) / 2
                    #butil.apply_transform(divider)
                    obj = divider
                else:
                    #obj.scale = (1, width / (w - w_), 1)
                    obj.location = -(l + l_) / 2, -(w + w_) / 2, -(h + h_) / 2
                    butil.apply_transform(obj, True)
                    obj.scale = (1, width / (w - w_), 1)
                for j in range(number - 1):
                    o_ = butil.deep_clone_obj(obj)
                    o_.location = location
                    butil.apply_transform(o_, True)
                    save_obj_parts_add(o_, self.ps.get("path"), self.ps.get("i"), "rack", first=False, use_bpy=True, parent_obj_id=parent_id, joint_info=joint_info, material=material)
                    location[1] += (width + gap)
                obj.location =  location
                butil.apply_transform(obj, True)
                return obj

            a = node_utils.save_geometry_new(
                assets,
                "rack",
                i,
                self.ps.get("i"),
                self.ps.get("path"),
                False,
                True,
                False,
                parent_obj_id=parent_id,
                joint_info=joint_info,
                material=material,
                apply=store_bbox_and_substitute_mesh
            )
            if a:
                first = False
        info = node_utils.store_info
        rack_1 = info["rack_1"]
        add_internal_bbox((rack_1[0], rack_1[1], rack_1[2], rack_1[3], self.params['Height'] - self.params['DoorThickness'], rack_1[4]))
        rack_last = info[f"rack_{self.params['RackAmount']}"]
        add_internal_bbox((rack_last[0], rack_last[1], rack_last[2], rack_last[3], rack_last[-1], self.params['DoorThickness']))
        add_joint(id_door, id_handle, {
            "name": get_joint_name("fixed"),
            "type": "fixed",
        })

        node_utils.save_geometry_new(assets, 'whole', 0, self.ps.get('i'), self.ps.get('path'), first, True, False)


@node_utils.to_nodegroup(
    "nodegroup_dish_rack", singleton=False, type="GeometryNodeTree"
)
def nodegroup_dish_rack(nw: NodeWrangler):

    # Code generated using version 2.6.5 of the node_transpiler

    quadrilateral = nw.new_node("GeometryNodeCurvePrimitiveQuadrilateral")

    curve_line = nw.new_node(
        Nodes.CurveLine,
        input_kwargs={
            "Start": (0.0000, -1.0000, 0.0000),
            "End": (0.0000, 1.0000, 0.0000),
        },
    )

    group_input = nw.new_node(
        Nodes.GroupInput,
        expose_input=[
            ("NodeSocketFloatDistance", "Depth", 2.0000),
            ("NodeSocketFloatDistance", "Width", 2.0000),
            ("NodeSocketFloatDistance", "Radius", 0.0200),
            ("NodeSocketInt", "Amount", 5),
            ("NodeSocketFloat", "Height", 0.5000),
        ],
    )

    combine_xyz_4 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={"Y": -1.0000, "Z": group_input.outputs["Height"]},
    )

    curve_line_1 = nw.new_node(
        Nodes.CurveLine,
        input_kwargs={"Start": (0.0000, -1.0000, 0.0000), "End": combine_xyz_4},
    )

    geometry_to_instance_1 = nw.new_node(
        "GeometryNodeGeometryToInstance", input_kwargs={"Geometry": curve_line_1}
    )

    multiply = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Amount"], 1: 2.0000},
        attrs={"operation": "MULTIPLY"},
    )

    duplicate_elements_2 = nw.new_node(
        Nodes.DuplicateElements,
        input_kwargs={"Geometry": geometry_to_instance_1, "Amount": multiply},
        attrs={"domain": "INSTANCE"},
    )

    divide = nw.new_node(
        Nodes.Math,
        input_kwargs={0: 1.0000, 1: group_input.outputs["Amount"]},
        attrs={"operation": "DIVIDE"},
    )

    multiply_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: duplicate_elements_2.outputs["Duplicate Index"], 1: divide},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_3 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"Y": multiply_1})

    set_position_2 = nw.new_node(
        Nodes.SetPosition,
        input_kwargs={
            "Geometry": duplicate_elements_2.outputs["Geometry"],
            "Offset": combine_xyz_3,
        },
    )

    join_geometry_1 = nw.new_node(
        Nodes.JoinGeometry, input_kwargs={"Geometry": [curve_line, set_position_2]}
    )

    geometry_to_instance = nw.new_node(
        "GeometryNodeGeometryToInstance", input_kwargs={"Geometry": join_geometry_1}
    )

    duplicate_elements = nw.new_node(
        Nodes.DuplicateElements,
        input_kwargs={"Geometry": geometry_to_instance, "Amount": multiply},
        attrs={"domain": "INSTANCE"},
    )

    subtract = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: duplicate_elements.outputs["Duplicate Index"],
            1: group_input.outputs["Amount"],
        },
        attrs={"operation": "SUBTRACT"},
    )

    multiply_2 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: subtract, 1: divide},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz = nw.new_node(Nodes.CombineXYZ, input_kwargs={"X": multiply_2})

    set_position = nw.new_node(
        Nodes.SetPosition,
        input_kwargs={
            "Geometry": duplicate_elements.outputs["Geometry"],
            "Offset": combine_xyz,
        },
    )

    transform_1 = nw.new_node(
        Nodes.Transform,
        input_kwargs={"Geometry": set_position, "Rotation": (0.0000, 0.0000, 1.5708)},
    )

    duplicate_elements_1 = nw.new_node(
        Nodes.DuplicateElements,
        input_kwargs={"Geometry": geometry_to_instance, "Amount": multiply},
        attrs={"domain": "INSTANCE"},
    )

    subtract_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: duplicate_elements_1.outputs["Duplicate Index"],
            1: group_input.outputs["Amount"],
        },
        attrs={"operation": "SUBTRACT"},
    )

    multiply_3 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: subtract_1, 1: divide},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_1 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"X": multiply_3})

    set_position_1 = nw.new_node(
        Nodes.SetPosition,
        input_kwargs={
            "Geometry": duplicate_elements_1.outputs["Geometry"],
            "Offset": combine_xyz_1,
        },
    )

    quadrilateral_1 = nw.new_node("GeometryNodeCurvePrimitiveQuadrilateral")

    multiply_4 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Height"], 1: 0.8000},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_5 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"Z": multiply_4})

    transform_2 = nw.new_node(
        Nodes.Transform,
        input_kwargs={"Geometry": quadrilateral_1, "Translation": combine_xyz_5},
    )

    join_geometry = nw.new_node(
        Nodes.JoinGeometry,
        input_kwargs={
            "Geometry": [quadrilateral, transform_1, set_position_1, transform_2]
        },
    )

    curve_circle = nw.new_node(
        Nodes.CurveCircle, input_kwargs={"Radius": group_input.outputs["Radius"]}
    )

    curve_to_mesh = nw.new_node(
        Nodes.CurveToMesh,
        input_kwargs={
            "Curve": join_geometry,
            "Profile Curve": curve_circle.outputs["Curve"],
            "Fill Caps": True,
        },
    )

    multiply_5 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Depth"]},
        attrs={"operation": "MULTIPLY"},
    )

    multiply_6 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Width"]},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_2 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": multiply_5, "Y": multiply_6, "Z": 0.5000}
    )

    transform = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": curve_to_mesh,
            "Rotation": (0.0000, 0.0000, 1.5708),
            "Scale": combine_xyz_2,
        },
    )

    group_output = nw.new_node(
        Nodes.GroupOutput,
        input_kwargs={"Mesh": transform},
        attrs={"is_active_output": True},
    )


@node_utils.to_nodegroup("nodegroup_text", singleton=False, type="GeometryNodeTree")
def nodegroup_text(nw: NodeWrangler):
    # Code generated using version 2.6.5 of the node_transpiler

    group_input = nw.new_node(
        Nodes.GroupInput,
        expose_input=[
            ("NodeSocketVectorTranslation", "Translation", (1.5000, 0.0000, 0.0000)),
            ("NodeSocketString", "String", "BrandName"),
            ("NodeSocketFloatDistance", "Size", 0.0500),
            ("NodeSocketFloat", "Offset Scale", 0.0020),
        ],
    )

    string_to_curves = nw.new_node(
        "GeometryNodeStringToCurves",
        input_kwargs={
            "String": group_input.outputs["String"],
            "Size": group_input.outputs["Size"],
        },
        attrs={"align_y": "BOTTOM_BASELINE", "align_x": "CENTER"},
    )

    fill_curve = nw.new_node(
        Nodes.FillCurve,
        input_kwargs={"Curve": string_to_curves.outputs["Curve Instances"]},
    )

    extrude_mesh = nw.new_node(
        Nodes.ExtrudeMesh,
        input_kwargs={
            "Mesh": fill_curve,
            "Offset Scale": group_input.outputs["Offset Scale"],
        },
    )

    transform_1 = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": extrude_mesh.outputs["Mesh"],
            "Translation": group_input.outputs["Translation"],
            "Rotation": (1.5708, 0.0000, 1.5708),
        },
    )

    group_output = nw.new_node(
        Nodes.GroupOutput,
        input_kwargs={"Geometry": transform_1},
        attrs={"is_active_output": True},
    )


@node_utils.to_nodegroup("nodegroup_handle", singleton=False, type="GeometryNodeTree")
def nodegroup_handle(nw: NodeWrangler):
    # Code generated using version 2.6.5 of the node_transpiler

    group_input = nw.new_node(
        Nodes.GroupInput,
        expose_input=[
            ("NodeSocketFloat", "width", 0.0000),
            ("NodeSocketFloat", "length", 0.0000),
            ("NodeSocketFloat", "thickness", 0.0200),
        ],
    )

    cube = nw.new_node(
        Nodes.MeshCube, input_kwargs={"Size": group_input.outputs["width"]}
    )

    store_named_attribute = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": cube.outputs["Mesh"],
            "Name": "uv_map",
            3: cube.outputs["UV Map"],
        },
        attrs={"domain": "CORNER", "data_type": "FLOAT_VECTOR"},
    )

    cube_1 = nw.new_node(
        Nodes.MeshCube, input_kwargs={"Size": group_input.outputs["width"]}
    )

    store_named_attribute_1 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": cube_1.outputs["Mesh"],
            "Name": "uv_map",
            3: cube_1.outputs["UV Map"],
        },
        attrs={"domain": "CORNER", "data_type": "FLOAT_VECTOR"},
    )

    combine_xyz = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"Y": group_input.outputs["length"]}
    )

    transform = nw.new_node(
        Nodes.Transform,
        input_kwargs={"Geometry": store_named_attribute_1, "Translation": combine_xyz},
    )

    join_geometry_1 = nw.new_node(
        Nodes.JoinGeometry,
        input_kwargs={"Geometry": [store_named_attribute, transform]},
    )

    multiply = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["width"]},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_3 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"Z": multiply})

    transform_2 = nw.new_node(
        Nodes.Transform,
        input_kwargs={"Geometry": join_geometry_1, "Translation": combine_xyz_3},
    )

    add = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: group_input.outputs["length"],
            1: group_input.outputs["width"],
        },
    )

    combine_xyz_1 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={
            "X": group_input.outputs["width"],
            "Y": add,
            "Z": group_input.outputs["thickness"],
        },
    )

    cube_2 = nw.new_node(Nodes.MeshCube, input_kwargs={"Size": combine_xyz_1})

    store_named_attribute_2 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": cube_2.outputs["Mesh"],
            "Name": "uv_map",
            3: cube_2.outputs["UV Map"],
        },
        attrs={"domain": "CORNER", "data_type": "FLOAT_VECTOR"},
    )

    multiply_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["length"]},
        attrs={"operation": "MULTIPLY"},
    )

    multiply_2 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["thickness"]},
        attrs={"operation": "MULTIPLY"},
    )

    add_1 = nw.new_node(
        Nodes.Math, input_kwargs={0: group_input.outputs["width"], 1: multiply_2}
    )

    combine_xyz_2 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"Y": multiply_1, "Z": add_1}
    )

    transform_1 = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": store_named_attribute_2,
            "Translation": combine_xyz_2,
        },
    )

    join_geometry = nw.new_node(
        Nodes.JoinGeometry, input_kwargs={"Geometry": [transform_2, transform_1]}
    )

    group_output = nw.new_node(
        Nodes.GroupOutput,
        input_kwargs={"Geometry": join_geometry},
        attrs={"is_active_output": True},
    )


@node_utils.to_nodegroup("nodegroup_center", singleton=False, type="GeometryNodeTree")
def nodegroup_center(nw: NodeWrangler):
    # Code generated using version 2.6.5 of the node_transpiler

    group_input = nw.new_node(
        Nodes.GroupInput,
        expose_input=[
            ("NodeSocketGeometry", "Geometry", None),
            ("NodeSocketVector", "Vector", (0.0000, 0.0000, 0.0000)),
            ("NodeSocketFloat", "MarginX", 0.5000),
            ("NodeSocketFloat", "MarginY", 0.0000),
            ("NodeSocketFloat", "MarginZ", 0.0000),
        ],
    )

    bounding_box = nw.new_node(
        Nodes.BoundingBox, input_kwargs={"Geometry": group_input.outputs["Geometry"]}
    )

    subtract = nw.new_node(
        Nodes.VectorMath,
        input_kwargs={0: group_input.outputs["Vector"], 1: bounding_box.outputs["Min"]},
        attrs={"operation": "SUBTRACT"},
    )

    separate_xyz = nw.new_node(
        Nodes.SeparateXYZ, input_kwargs={"Vector": subtract.outputs["Vector"]}
    )

    greater_than = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["X"], 1: group_input.outputs["MarginX"]},
        attrs={"operation": "GREATER_THAN", "use_clamp": True},
    )

    subtract_1 = nw.new_node(
        Nodes.VectorMath,
        input_kwargs={0: bounding_box.outputs["Max"], 1: group_input.outputs["Vector"]},
        attrs={"operation": "SUBTRACT"},
    )

    separate_xyz_1 = nw.new_node(
        Nodes.SeparateXYZ, input_kwargs={"Vector": subtract_1.outputs["Vector"]}
    )

    greater_than_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: separate_xyz_1.outputs["X"],
            1: group_input.outputs["MarginX"],
        },
        attrs={"operation": "GREATER_THAN", "use_clamp": True},
    )

    op_and = nw.new_node(
        Nodes.BooleanMath, input_kwargs={0: greater_than, 1: greater_than_1}
    )

    greater_than_2 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["Y"], 1: group_input.outputs["MarginY"]},
        attrs={"operation": "GREATER_THAN"},
    )

    greater_than_3 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: separate_xyz_1.outputs["Y"],
            1: group_input.outputs["MarginY"],
        },
        attrs={"operation": "GREATER_THAN", "use_clamp": True},
    )

    op_and_1 = nw.new_node(
        Nodes.BooleanMath, input_kwargs={0: greater_than_2, 1: greater_than_3}
    )

    op_and_2 = nw.new_node(Nodes.BooleanMath, input_kwargs={0: op_and, 1: op_and_1})

    greater_than_4 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["Z"], 1: group_input.outputs["MarginZ"]},
        attrs={"operation": "GREATER_THAN", "use_clamp": True},
    )

    greater_than_5 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: separate_xyz_1.outputs["Z"],
            1: group_input.outputs["MarginZ"],
        },
        attrs={"operation": "GREATER_THAN", "use_clamp": True},
    )

    op_and_3 = nw.new_node(
        Nodes.BooleanMath, input_kwargs={0: greater_than_4, 1: greater_than_5}
    )

    op_and_4 = nw.new_node(Nodes.BooleanMath, input_kwargs={0: op_and_2, 1: op_and_3})

    op_not = nw.new_node(
        Nodes.BooleanMath, input_kwargs={0: op_and_4}, attrs={"operation": "NOT"}
    )

    group_output = nw.new_node(
        Nodes.GroupOutput,
        input_kwargs={"In": op_and_4, "Out": op_not},
        attrs={"is_active_output": True},
    )


@node_utils.to_nodegroup("nodegroup_cube", singleton=False, type="GeometryNodeTree")
def nodegroup_cube(nw: NodeWrangler):
    # Code generated using version 2.6.5 of the node_transpiler

    group_input = nw.new_node(
        Nodes.GroupInput,
        expose_input=[
            ("NodeSocketVectorTranslation", "Size", (0.1000, 10.0000, 4.0000)),
            ("NodeSocketVector", "Pos", (0.0000, 0.0000, 0.0000)),
            ("NodeSocketInt", "Resolution", 2),
        ],
    )

    cube = nw.new_node(
        Nodes.MeshCube,
        input_kwargs={
            "Size": group_input.outputs["Size"],
            "Vertices X": group_input.outputs["Resolution"],
            "Vertices Y": group_input.outputs["Resolution"],
            "Vertices Z": group_input.outputs["Resolution"],
        },
    )

    store_named_attribute_1 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": cube.outputs["Mesh"],
            "Name": "uv_map",
            3: cube.outputs["UV Map"],
        },
        attrs={"domain": "CORNER", "data_type": "FLOAT_VECTOR"},
    )

    store_named_attribute = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={"Geometry": store_named_attribute_1, "Name": "uv_map"},
        attrs={"domain": "CORNER", "data_type": "FLOAT_VECTOR"},
    )

    multiply_add = nw.new_node(
        Nodes.VectorMath,
        input_kwargs={
            0: group_input.outputs["Size"],
            1: (0.5000, 0.5000, 0.5000),
            2: group_input.outputs["Pos"],
        },
        attrs={"operation": "MULTIPLY_ADD"},
    )

    transform = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": store_named_attribute,
            "Translation": multiply_add.outputs["Vector"],
        },
    )

    group_output = nw.new_node(
        Nodes.GroupOutput,
        input_kwargs={"Geometry": transform},
        attrs={"is_active_output": True},
    )


@node_utils.to_nodegroup(
    "nodegroup_hollow_cube", singleton=False, type="GeometryNodeTree"
)
def nodegroup_hollow_cube(nw: NodeWrangler):
    # Code generated using version 2.6.5 of the node_transpiler

    group_input = nw.new_node(
        Nodes.GroupInput,
        expose_input=[
            ("NodeSocketVectorTranslation", "Size", (0.1000, 10.0000, 4.0000)),
            ("NodeSocketVector", "Pos", (0.0000, 0.0000, 0.0000)),
            ("NodeSocketInt", "Resolution", 2),
            ("NodeSocketFloat", "Thickness", 0.0000),
            ("NodeSocketBool", "Switch1", False),
            ("NodeSocketBool", "Switch2", False),
            ("NodeSocketBool", "Switch3", False),
            ("NodeSocketBool", "Switch4", False),
            ("NodeSocketBool", "Switch5", False),
            ("NodeSocketBool", "Switch6", False),
        ],
    )

    separate_xyz = nw.new_node(
        Nodes.SeparateXYZ, input_kwargs={"Vector": group_input.outputs["Size"]}
    )

    multiply = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Thickness"], 1: 2.0000},
        attrs={"operation": "MULTIPLY"},
    )

    subtract = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["Y"], 1: multiply},
        attrs={"operation": "SUBTRACT"},
    )

    subtract_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["Z"], 1: multiply},
        attrs={"operation": "SUBTRACT"},
    )

    combine_xyz_4 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={
            "X": group_input.outputs["Thickness"],
            "Y": subtract,
            "Z": subtract_1,
        },
    )

    cube_2 = nw.new_node(
        Nodes.MeshCube,
        input_kwargs={
            "Size": combine_xyz_4,
            "Vertices X": group_input.outputs["Resolution"],
            "Vertices Y": group_input.outputs["Resolution"],
            "Vertices Z": group_input.outputs["Resolution"],
        },
    )

    store_named_attribute_1 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": cube_2.outputs["Mesh"],
            "Name": "uv_map",
            3: cube_2.outputs["UV Map"],
        },
        attrs={"domain": "CORNER", "data_type": "FLOAT_VECTOR"},
    )

    multiply_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Thickness"]},
        attrs={"operation": "MULTIPLY"},
    )

    separate_xyz_1 = nw.new_node(
        Nodes.SeparateXYZ, input_kwargs={"Vector": group_input.outputs["Pos"]}
    )

    add = nw.new_node(
        Nodes.Math, input_kwargs={0: multiply_1, 1: separate_xyz_1.outputs["X"]}
    )

    scale = nw.new_node(
        Nodes.VectorMath,
        input_kwargs={0: group_input.outputs["Size"], "Scale": 0.5000},
        attrs={"operation": "SCALE"},
    )

    separate_xyz_2 = nw.new_node(
        Nodes.SeparateXYZ, input_kwargs={"Vector": scale.outputs["Vector"]}
    )

    add_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_2.outputs["Y"], 1: separate_xyz_1.outputs["Y"]},
    )

    subtract_2 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_2.outputs["Z"], 1: separate_xyz_1.outputs["Z"]},
        attrs={"operation": "SUBTRACT"},
    )

    combine_xyz_5 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": add, "Y": add_1, "Z": subtract_2}
    )

    transform_2 = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": store_named_attribute_1,
            "Translation": combine_xyz_5,
        },
    )

    switch_2 = nw.new_node(
        Nodes.Switch, input_kwargs={1: group_input.outputs["Switch3"], 14: transform_2}
    )

    subtract_3 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["Y"], 1: multiply},
        attrs={"operation": "SUBTRACT"},
    )

    combine_xyz_2 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={
            "X": separate_xyz.outputs["X"],
            "Y": subtract_3,
            "Z": group_input.outputs["Thickness"],
        },
    )

    cube_1 = nw.new_node(
        Nodes.MeshCube,
        input_kwargs={
            "Size": combine_xyz_2,
            "Vertices X": group_input.outputs["Resolution"],
            "Vertices Y": group_input.outputs["Resolution"],
            "Vertices Z": group_input.outputs["Resolution"],
        },
    )

    store_named_attribute_4 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": cube_1.outputs["Mesh"],
            "Name": "uv_map",
            3: cube_1.outputs["UV Map"],
        },
        attrs={"domain": "CORNER", "data_type": "FLOAT_VECTOR"},
    )

    add_2 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_2.outputs["X"], 1: separate_xyz_1.outputs["X"]},
    )

    add_3 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_2.outputs["Y"], 1: separate_xyz_1.outputs["Y"]},
    )

    subtract_4 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["Z"], 1: multiply_1},
        attrs={"operation": "SUBTRACT"},
    )

    combine_xyz_3 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": add_2, "Y": add_3, "Z": subtract_4}
    )

    transform_1 = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": store_named_attribute_4,
            "Translation": combine_xyz_3,
        },
    )

    switch_1 = nw.new_node(
        Nodes.Switch, input_kwargs={1: group_input.outputs["Switch2"], 14: transform_1}
    )

    subtract_5 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["Y"], 1: multiply},
        attrs={"operation": "SUBTRACT"},
    )

    combine_xyz = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={
            "X": separate_xyz.outputs["X"],
            "Y": subtract_5,
            "Z": group_input.outputs["Thickness"],
        },
    )

    cube = nw.new_node(
        Nodes.MeshCube,
        input_kwargs={
            "Size": combine_xyz,
            "Vertices X": group_input.outputs["Resolution"],
            "Vertices Y": group_input.outputs["Resolution"],
            "Vertices Z": group_input.outputs["Resolution"],
        },
    )

    store_named_attribute = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": cube.outputs["Mesh"],
            "Name": "uv_map",
            3: cube.outputs["UV Map"],
        },
        attrs={"domain": "CORNER", "data_type": "FLOAT_VECTOR"},
    )

    add_4 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_2.outputs["X"], 1: separate_xyz_1.outputs["X"]},
    )

    add_5 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_2.outputs["Y"], 1: separate_xyz_1.outputs["Y"]},
    )

    add_6 = nw.new_node(
        Nodes.Math, input_kwargs={0: multiply_1, 1: separate_xyz_1.outputs["Z"]}
    )

    combine_xyz_1 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": add_4, "Y": add_5, "Z": add_6}
    )

    transform = nw.new_node(
        Nodes.Transform,
        input_kwargs={"Geometry": store_named_attribute, "Translation": combine_xyz_1},
    )

    switch = nw.new_node(
        Nodes.Switch, input_kwargs={1: group_input.outputs["Switch1"], 14: transform}
    )

    subtract_6 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["Y"], 1: multiply},
        attrs={"operation": "SUBTRACT"},
    )

    subtract_7 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["Z"], 1: multiply},
        attrs={"operation": "SUBTRACT"},
    )

    combine_xyz_6 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={
            "X": group_input.outputs["Thickness"],
            "Y": subtract_6,
            "Z": subtract_7,
        },
    )

    cube_3 = nw.new_node(
        Nodes.MeshCube,
        input_kwargs={
            "Size": combine_xyz_6,
            "Vertices X": group_input.outputs["Resolution"],
            "Vertices Y": group_input.outputs["Resolution"],
            "Vertices Z": group_input.outputs["Resolution"],
        },
    )

    store_named_attribute_5 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": cube_3.outputs["Mesh"],
            "Name": "uv_map",
            3: cube_3.outputs["UV Map"],
        },
        attrs={"domain": "CORNER", "data_type": "FLOAT_VECTOR"},
    )

    subtract_8 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["X"], 1: multiply_1},
        attrs={"operation": "SUBTRACT"},
    )

    add_7 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_2.outputs["Y"], 1: separate_xyz_1.outputs["Y"]},
    )

    subtract_9 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_2.outputs["Z"], 1: separate_xyz_1.outputs["Z"]},
        attrs={"operation": "SUBTRACT"},
    )

    combine_xyz_7 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": subtract_8, "Y": add_7, "Z": subtract_9}
    )

    transform_3 = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": store_named_attribute_5,
            "Translation": combine_xyz_7,
        },
    )

    switch_3 = nw.new_node(
        Nodes.Switch, input_kwargs={1: group_input.outputs["Switch4"], 14: transform_3}
    )

    combine_xyz_9 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={
            "X": separate_xyz.outputs["X"],
            "Y": group_input.outputs["Thickness"],
            "Z": separate_xyz.outputs["Z"],
        },
    )

    cube_4 = nw.new_node(
        Nodes.MeshCube,
        input_kwargs={
            "Size": combine_xyz_9,
            "Vertices X": group_input.outputs["Resolution"],
            "Vertices Y": group_input.outputs["Resolution"],
            "Vertices Z": group_input.outputs["Resolution"],
        },
    )

    store_named_attribute_2 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": cube_4.outputs["Mesh"],
            "Name": "uv_map",
            3: cube_4.outputs["UV Map"],
        },
        attrs={"domain": "CORNER", "data_type": "FLOAT_VECTOR"},
    )

    add_8 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_1.outputs["X"], 1: separate_xyz_2.outputs["X"]},
    )

    add_9 = nw.new_node(
        Nodes.Math, input_kwargs={0: separate_xyz_1.outputs["Y"], 1: multiply_1}
    )

    add_10 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_1.outputs["Z"], 1: separate_xyz_2.outputs["Z"]},
    )

    combine_xyz_8 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": add_8, "Y": add_9, "Z": add_10}
    )

    transform_4 = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": store_named_attribute_2,
            "Translation": combine_xyz_8,
        },
    )

    switch_4 = nw.new_node(
        Nodes.Switch, input_kwargs={1: group_input.outputs["Switch5"], 14: transform_4}
    )

    combine_xyz_10 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={
            "X": separate_xyz.outputs["X"],
            "Y": group_input.outputs["Thickness"],
            "Z": separate_xyz.outputs["Z"],
        },
    )

    cube_5 = nw.new_node(
        Nodes.MeshCube,
        input_kwargs={
            "Size": combine_xyz_10,
            "Vertices X": group_input.outputs["Resolution"],
            "Vertices Y": group_input.outputs["Resolution"],
            "Vertices Z": group_input.outputs["Resolution"],
        },
    )

    store_named_attribute_3 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": cube_5.outputs["Mesh"],
            "Name": "uv_map",
            3: cube_5.outputs["UV Map"],
        },
        attrs={"domain": "CORNER", "data_type": "FLOAT_VECTOR"},
    )

    add_11 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_2.outputs["X"], 1: separate_xyz_1.outputs["X"]},
    )

    subtract_10 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["Y"], 1: multiply_1},
        attrs={"operation": "SUBTRACT"},
    )

    add_12 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz_2.outputs["Z"], 1: separate_xyz_1.outputs["Z"]},
    )

    combine_xyz_11 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": add_11, "Y": subtract_10, "Z": add_12}
    )

    transform_5 = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": store_named_attribute_3,
            "Translation": combine_xyz_11,
        },
    )

    switch_5 = nw.new_node(
        Nodes.Switch, input_kwargs={1: group_input.outputs["Switch6"], 14: transform_5}
    )

    join_geometry = nw.new_node(
        Nodes.JoinGeometry,
        input_kwargs={
            "Geometry": [
                switch_2.outputs[6],
                switch_1.outputs[6],
                switch.outputs[6],
                switch_3.outputs[6],
                switch_4.outputs[6],
                switch_5.outputs[6],
            ]
        },
    )

    group_output = nw.new_node(
        Nodes.GroupOutput,
        input_kwargs={"Geometry": join_geometry},
        attrs={"is_active_output": True},
    )


@node_utils.to_nodegroup(
    "nodegroup_dishwasher_geometry", singleton=False, type="GeometryNodeTree"
)
def nodegroup_dishwasher_geometry(nw: NodeWrangler, preprocess: bool = False, return_type_name=""):
    # Code generated using version 2.6.5 of the node_transpiler

    group_input = nw.new_node(
        Nodes.GroupInput,
        expose_input=[
            ("NodeSocketFloat", "Depth", 1.0000),
            ("NodeSocketFloat", "Width", 1.0000),
            ("NodeSocketFloat", "Height", 1.0000),
            ("NodeSocketFloat", "DoorThickness", 0.0700),
            ("NodeSocketFloat", "DoorRotation", 0.0000),
            ("NodeSocketFloatDistance", "RackRadius", 0.0100),
            ("NodeSocketInt", "RackAmount", 2),
            ("NodeSocketString", "BrandName", "BrandName"),
            ("NodeSocketMaterial", "Surface", None),
            ("NodeSocketMaterial", "Front", None),
            ("NodeSocketMaterial", "Top", None),
            ("NodeSocketMaterial", "WhiteMetal", None),
            ("NodeSocketMaterial", "NameMaterial", None),
        ],
    )

    combine_xyz = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={
            "X": group_input.outputs["Depth"],
            "Y": group_input.outputs["Width"],
            "Z": group_input.outputs["Height"],
        },
    )

    hollowcube = nw.new_node(
        nodegroup_hollow_cube().name,
        input_kwargs={
            "Size": combine_xyz,
            "Thickness": group_input.outputs["DoorThickness"],
            "Switch2": True,
            "Switch4": True,
        },
    )

    set_material_1 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": hollowcube,
            "Material": group_input.outputs["Surface"],
        },
    )

    subdivide_mesh = nw.new_node(
        Nodes.SubdivideMesh, input_kwargs={"Mesh": set_material_1, "Level": 0}
    )

    # set_shade_smooth_2 = nw.new_node(Nodes.SetShadeSmooth, input_kwargs={'Geometry': subdivide_mesh})

    body = nw.new_node(
        Nodes.Reroute, input_kwargs={"Input": subdivide_mesh}, label="Body"
    )

    combine_xyz_1 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={
            "X": group_input.outputs["DoorThickness"],
            "Y": group_input.outputs["Width"],
            "Z": group_input.outputs["Height"],
        },
    )

    combine_xyz_2 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": group_input.outputs["Depth"]}
    )

    cube = nw.new_node(
        nodegroup_cube().name,
        input_kwargs={"Size": combine_xyz_1, "Pos": combine_xyz_2},
    )

    position = nw.new_node(Nodes.InputPosition)

    center = nw.new_node(
        nodegroup_center().name,
        input_kwargs={
            "Geometry": cube,
            "Vector": position,
            "MarginX": -1.0000,
            "MarginY": 0.1000,
            "MarginZ": 0.1500,
        },
    )

    set_material_2 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": cube,
            "Selection": center.outputs["In"],
            "Material": group_input.outputs["Front"],
        },
    )

    set_material_3 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": set_material_2,
            "Selection": center.outputs["Out"],
            "Material": group_input.outputs["Surface"],
        },
    )

    store_part = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={"Geometry": center.outputs["In"], "Name": "In", "Value": 1},
        attrs={"domain": "FACE", "data_type": "INT"},
    )
    store_part_1 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={"Geometry": center.outputs["Out"], "Name": "Out", "Value": 1},
        attrs={"domain": "FACE", "data_type": "INT"},
    )

    set_material_3 = nw.new_node(
        Nodes.JoinGeometry,
        input_kwargs={"Geometry": [store_part, store_part_1, set_material_3]},
    )


    # set_shade_smooth = nw.new_node(Nodes.SetShadeSmooth, input_kwargs={'Geometry': set_material_3})

    multiply = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Width"], 1: 0.0500},
        attrs={"operation": "MULTIPLY"},
    )

    multiply_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Width"], 1: 0.8000},
        attrs={"operation": "MULTIPLY"},
    )

    multiply_2 = nw.new_node(
        Nodes.Math, input_kwargs={0: multiply}, attrs={"operation": "MULTIPLY"}
    )

    handle = nw.new_node(
        nodegroup_handle().name,
        input_kwargs={"width": multiply, "length": multiply_1, "thickness": multiply_2},
    )

    add = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: group_input.outputs["Depth"],
            1: group_input.outputs["DoorThickness"],
        },
    )

    multiply_3 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Width"], 1: 0.1000},
        attrs={"operation": "MULTIPLY"},
    )

    multiply_4 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Height"], 1: 0.9500},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_13 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": add, "Y": multiply_3, "Z": multiply_4}
    )

    transform_1 = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": handle,
            "Translation": combine_xyz_13,
            "Rotation": (0.0000, 1.5708, 0.0000),
        },
    )

    set_material_8 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": transform_1,
            "Material": group_input.outputs["WhiteMetal"],
        },
    )

    add_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: group_input.outputs["Depth"],
            1: group_input.outputs["DoorThickness"],
        },
    )

    multiply_5 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Width"]},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_12 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": add_1, "Y": multiply_5, "Z": 0.0300}
    )

    multiply_6 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Height"], 1: 0.0500},
        attrs={"operation": "MULTIPLY"},
    )

    text = nw.new_node(
        nodegroup_text().name,
        input_kwargs={
            "Translation": combine_xyz_12,
            "String": group_input.outputs["BrandName"],
            "Size": multiply_6,
        },
    )

    text = complete_no_bevel(nw, text, preprocess)

    set_material_9 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": text,
            "Material": group_input.outputs["NameMaterial"],
        },
    )

    set_material_8 = complete_bevel(nw, set_material_8, preprocess)
    set_material_8 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={"Geometry": set_material_8, "Name": "handle", "Value": 1},
        attrs={"domain": "FACE", "data_type": "INT"},
    )
    set_material_9 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={"Geometry": set_material_9, "Name": "brand", "Value": 1},
        attrs={"domain": "FACE", "data_type": "INT"},
    )

    if return_type_name == "handle":
        body = nw.new_node(Nodes.RealizeInstances, [set_material_8])
        group_output = nw.new_node(Nodes.GroupOutput, input_kwargs={"Geometry": body})
        return 

    join_geometry_3 = nw.new_node(
        Nodes.JoinGeometry,
        input_kwargs={"Geometry": [set_material_3, set_material_9]},
    )

    geometry_to_instance = nw.new_node(
        "GeometryNodeGeometryToInstance", input_kwargs={"Geometry": join_geometry_3}
    )

    y = nw.scalar_multiply(
        group_input.outputs["DoorRotation"], 1 if not preprocess else 0
    )

    combine_xyz_3 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"Y": y})

    combine_xyz_4 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": group_input.outputs["Depth"]}
    )

    rotate_instances = nw.new_node(
        Nodes.RotateInstances,
        input_kwargs={
            "Instances": geometry_to_instance,
            "Rotation": combine_xyz_3,
            "Pivot Point": combine_xyz_4,
        },
    )

    rotate_instances = nw.new_node(Nodes.RealizeInstances, [rotate_instances])

    door = nw.new_node(
        Nodes.Reroute, input_kwargs={"Input": rotate_instances}, label="door"
    )

    multiply_7 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["DoorThickness"], 1: 2.1000},
        attrs={"operation": "MULTIPLY"},
    )

    subtract = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Depth"], 1: multiply_7},
        attrs={"operation": "SUBTRACT"},
    )

    multiply_8 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["DoorThickness"], 1: 2.1000},
        attrs={"operation": "MULTIPLY"},
    )

    subtract_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Width"], 1: multiply_8},
        attrs={"operation": "SUBTRACT"},
    )

    dishrack = nw.new_node(
        nodegroup_dish_rack().name,
        input_kwargs={
            "Depth": subtract_1,
            "Width": subtract,
            "Radius": group_input.outputs["RackRadius"],
            "Amount": 4,
            "Height": 0.1000,
        },
    )

    geometry_to_instance_1 = nw.new_node(
        "GeometryNodeGeometryToInstance", input_kwargs={"Geometry": dishrack}
    )

    duplicate_elements = nw.new_node(
        Nodes.DuplicateElements,
        input_kwargs={
            "Geometry": geometry_to_instance_1,
            "Amount": group_input.outputs["RackAmount"],
        },
        attrs={"domain": "INSTANCE"},
    )

    ids = nw.new_node(
        Nodes.Math,
        input_kwargs={0: duplicate_elements.outputs["Duplicate Index"], 1: 1.0000},
    )


    store = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": duplicate_elements,
            "Name": "rack",
            "Value": ids,
        },
        attrs={"domain": "INSTANCE", "data_type": "INT"},
    )

    multiply_9 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Depth"]},
        attrs={"operation": "MULTIPLY"},
    )

    multiply_10 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Width"]},
        attrs={"operation": "MULTIPLY"},
    )

    #print(duplicate_elements.outputs["Duplicate Index"])

    add_2 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: duplicate_elements.outputs["Duplicate Index"], 1: 1.0000},
    )

    multiply_11 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["DoorThickness"], 1: 2.0000},
        attrs={"operation": "MULTIPLY"},
    )

    subtract_2 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Height"], 1: multiply_11},
        attrs={"operation": "SUBTRACT"},
    )

    add_3 = nw.new_node(
        Nodes.Math, input_kwargs={0: group_input.outputs["RackAmount"], 1: 1.0000}
    )

    divide = nw.new_node(
        Nodes.Math,
        input_kwargs={0: subtract_2, 1: add_3},
        attrs={"operation": "DIVIDE"},
    )

    multiply_12 = nw.new_node(
        Nodes.Math, input_kwargs={0: add_2, 1: divide}, attrs={"operation": "MULTIPLY"}
    )

    combine_xyz_5 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={"X": multiply_9, "Y": multiply_10, "Z": multiply_12},
    )

    set_position = nw.new_node(
        Nodes.SetPosition,
        input_kwargs={
            "Geometry": store.outputs["Geometry"],
            "Offset": combine_xyz_5,
        },
    )

    set_material = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": set_position,
            "Material": group_input.outputs["Surface"],
        },
    )

    set_material = nw.new_node(Nodes.RealizeInstances, [set_material])

    racks = nw.new_node(
        Nodes.Reroute, input_kwargs={"Input": set_material}, label="racks"
    )

    add_4 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: group_input.outputs["Depth"],
            1: group_input.outputs["DoorThickness"],
        },
    )

    reroute_10 = nw.new_node(Nodes.Reroute, input_kwargs={"Input": add_4})

    reroute_11 = nw.new_node(
        Nodes.Reroute, input_kwargs={"Input": group_input.outputs["Width"]}
    )

    reroute_8 = nw.new_node(
        Nodes.Reroute, input_kwargs={"Input": group_input.outputs["DoorThickness"]}
    )

    combine_xyz_6 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={"X": reroute_10, "Y": reroute_11, "Z": reroute_8},
    )

    reroute_9 = nw.new_node(
        Nodes.Reroute, input_kwargs={"Input": group_input.outputs["Height"]}
    )

    combine_xyz_7 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"Z": reroute_9})

    cube_1 = nw.new_node(
        nodegroup_cube().name,
        input_kwargs={"Size": combine_xyz_6, "Pos": combine_xyz_7},
    )

    set_material_5 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={"Geometry": cube_1, "Material": group_input.outputs["Top"]},
    )

    # set_shade_smooth_1 = nw.new_node(Nodes.SetShadeSmooth, input_kwargs={'Geometry': set_material_5})

    join_geometry_2 = nw.new_node(
        Nodes.JoinGeometry, input_kwargs={"Geometry": set_material_5}
    )

    heater = nw.new_node(
        Nodes.Reroute, input_kwargs={"Input": join_geometry_2}, label="heater"
    )

    store_1 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": body,
            "Name": "part",
            "Value": 1,
        },
    )

    if return_type_name == "body":
        body = nw.new_node(Nodes.RealizeInstances, [body])
        group_output = nw.new_node(Nodes.GroupOutput, input_kwargs={"Geometry": body})
        return 

    store_2 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": door,
            "Name": "part",
            "Value": 2,
        },
    )

    if return_type_name == "door":
        door = nw.new_node(Nodes.RealizeInstances, [door])
        group_output = nw.new_node(Nodes.GroupOutput, input_kwargs={"Geometry": door})
        return

    # store_3 = nw.new_node(
    #     Nodes.StoreNamedAttribute,
    #     input_kwargs={
    #         "Geometry": racks,
    #         "Name": "part",
    #         "Value": 3,
    #     },
    # )

    store_4 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": heater,
            "Name": "part",
            "Value": 4,
        },
    )

    if return_type_name == "heater":
        heater = nw.new_node(Nodes.RealizeInstances, [heater])
        group_output = nw.new_node(Nodes.GroupOutput, input_kwargs={"Geometry": heater})
        return

    join_geometry = nw.new_node(
        Nodes.JoinGeometry, input_kwargs={"Geometry": [store_1, store_2, racks, store_4]}
    )

    geometry = nw.new_node(Nodes.RealizeInstances, [join_geometry])

    group_output = nw.new_node(Nodes.GroupOutput, input_kwargs={"Geometry": geometry})
