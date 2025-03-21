# Copyright (C) 2024, Princeton University.
# This source code is licensed under the BSD 3-Clause license found in the LICENSE file in the root directory of this source tree.

# Authors: Hongyu Wen


import numpy as np
from numpy.random import uniform as U

from infinigen.assets.material_assignments import AssetList
from infinigen.assets.utils.decorate import read_co
from infinigen.assets.utils.misc import generate_text
from infinigen.assets.utils.object import (
    get_joint_name,
    join_objects,
    save_obj_parts_add
)
from infinigen.core import surface
from infinigen.core.nodes import node_utils
from infinigen.core.nodes.node_wrangler import Nodes, NodeWrangler
from infinigen.core.placement.factory import AssetFactory
from infinigen.core.util import blender as butil
from infinigen.core.util.bevelling import add_bevel, complete_no_bevel, get_bevel_edges
from infinigen.core.util.blender import delete
from infinigen.core.util.math import FixedSeed
import bpy
import random
from infinigen.assets.utils.auxiliary_parts import random_auxiliary


class MicrowaveFactory(AssetFactory):
    def __init__(self, factory_seed, coarse=False, dimensions=[1.0, 1.0, 1.0]):
        super(MicrowaveFactory, self).__init__(factory_seed, coarse=coarse)

        self.dimensions = dimensions
        with FixedSeed(factory_seed):
            self.params = self.sample_parameters(dimensions)
            self.shaders, self.material_params, self.scratch, self.edge_wear = (
                self.get_material_params()
            )
        self.params.update(self.material_params)
        self.use_aux_botton = np.random.choice([True, False], p=[0.8, 0.2])
        if self.use_aux_botton:
            self.aux_botton = random_auxiliary("revolute_botton")

    def get_material_params(self):
        material_assignments = AssetList["MicrowaveFactory"]()
        params = {
            "Surface": material_assignments["surface"].assign_material(),
            "Back": material_assignments["back"].assign_material(),
            "BlackGlass": material_assignments["black_glass"].assign_material(),
            "Glass": material_assignments["glass"].assign_material(),
            "Rotate": material_assignments["rotate_surface"].assign_material(),
        }
        wrapped_params = {
            k: surface.shaderfunc_to_material(v) for k, v in params.items() if k != 'Rotate'
        }

        params = {f"{k}_": v for k, v in params.items()}

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
        depth = U(0.5, 0.7)
        width = U(0.6, 1.0)
        height = U(0.35, 0.45)
        panel_width = U(0.2, 0.4)
        margin_z = U(0.05, 0.1)
        door_thickness = U(0.02, 0.04)
        door_margin = U(0.03, 0.1)
        door_rotation = 0#-np.pi / 1.5  # Set to 0 for now
        brand_name = generate_text()
        params = {
            "Depth": depth,
            "Width": width,
            "Height": height,
            "PanelWidth": panel_width,
            "MarginZ": margin_z,
            "DoorThickness": door_thickness,
            "DoorMargin": door_margin,
            "DoorRotation": door_rotation,
            "BrandName": brand_name,
        }
        return params

    def create_asset(self, **params):
        self.button_lines = random.randint(1, 3)
        obj = butil.spawn_cube()
        butil.modify_mesh(
            obj,
            "NODES",
            node_group=nodegroup_microwave_geometry(preprocess=True),
            ng_inputs=self.params,
            apply=True,
        )
        bevel_edges = get_bevel_edges(obj)
        delete(obj)
        obj = butil.spawn_cube()
        butil.modify_mesh(
            obj,
            "NODES",
            node_group=nodegroup_microwave_geometry(),
            ng_inputs=self.params,
            apply=True,
        )
        obj = add_bevel(obj, bevel_edges)
        #self.params.update(params)
        self.ps = params

        return obj

    def finalize_assets(self, assets):
        # if self.scratch:
        #     self.scratch.apply(assets)
        # if self.edge_wear:
        #     self.edge_wear.apply(assets)
        material = []
        first = True
        for i in range(1, 6):
            if i == 1:
                material = []
                parent_id = "world"
                joint_info = {
                    "name": get_joint_name("fixed"),
                    "type": "fixed",
                }
                try: 
                    text = butil.spawn_cube()
                    butil.modify_mesh(
                        text,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="text", preprocess=True),
                        ng_inputs=self.params,
                        apply=True,
                    )
                    bevel_edges = get_bevel_edges(text)
                    delete(text)
                    text = butil.spawn_cube()
                    butil.modify_mesh(
                        text,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="text"),
                        ng_inputs=self.params,
                        apply=True,
                    )
                    text = add_bevel(text, bevel_edges)
                    co_text = read_co(text)
                except:
                    text = butil.spawn_cube()
                    butil.modify_mesh(
                        text,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="text"),
                        ng_inputs=self.params,
                        apply=True,
                    )
                    co_text = read_co(text)
                save_obj_parts_add([text], self.ps['path'], self.ps['i'], "text", first=True, use_bpy=True, parent_obj_id=parent_id, joint_info=joint_info, material=material)
            elif i == 2:
                material = None#[self.shaders['Back_']]
                parent_id = "world"
                joint_info = {
                    "name": get_joint_name("fixed"),
                    "type": "fixed",
                }
                try:
                    body = butil.spawn_cube()
                    butil.modify_mesh(
                        body,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="body", preprocess=True),
                        ng_inputs=self.params,
                        apply=True,
                    )
                    bevel_edges = get_bevel_edges(body)
                    delete(body)
                    body = butil.spawn_cube()
                    butil.modify_mesh(
                        body,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="body"),
                        ng_inputs=self.params,
                        apply=True,
                    )
                    body = add_bevel(body, bevel_edges)
                except:
                    body = butil.spawn_cube()
                    butil.modify_mesh(
                        body,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="body"),
                        ng_inputs=self.params,
                        apply=True,
                    )
                save_obj_parts_add([body], self.ps['path'], self.ps['i'], "microwave_body", first=False, use_bpy=True, parent_obj_id=parent_id, joint_info=joint_info, material=material)
            elif i == 3:
                material = None#[[self.shaders['Surface_'], "Out"], [self.shaders['BlackGlass_'], "In"]]
                parent_id = "world"
                joint_info = {
                    "name": get_joint_name("revolute"),
                    "type": "revolute",
                    "axis": (0, 0, 1),
                    "limit": {
                        "lower": -1.5708,
                        "upper": 0,
                    },
                    "origin_shift": (-self.params['DoorThickness'] / 2, -(self.params['Width'] - self.params['PanelWidth']) *(0.49), 0),
                }
                try: 
                    door = butil.spawn_cube()
                    butil.modify_mesh(
                        door,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="door", preprocess=True),
                        ng_inputs=self.params,
                        apply=True,
                    )
                    bevel_edges = get_bevel_edges(door)
                    delete(door)
                    door = butil.spawn_cube()
                    butil.modify_mesh(
                        door,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="door"),
                        ng_inputs=self.params,
                        apply=True,
                    )
                    door = add_bevel(door, bevel_edges)
                except:
                    door = butil.spawn_cube()
                    butil.modify_mesh(
                        door,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="door"),
                        ng_inputs=self.params,
                        apply=True,
                    )
                #door.location[0] += 0.02
                butil.apply_transform(door, True)
                save_obj_parts_add([door], self.ps['path'], self.ps['i'], "door", first=False, use_bpy=True, parent_obj_id=parent_id, joint_info=joint_info, material=material)
            elif i == 4:
                material = None #[self.shaders['Glass_']]
                parent_id = "world"
                joint_info = {
                    "name": get_joint_name("continuous"),
                    "type": "continuous",
                    "axis": (0, 0, 1)
                }
                try:
                    plate = butil.spawn_cube()
                    butil.modify_mesh(
                        plate,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="plate", preprocess=True),
                        ng_inputs=self.params,
                        apply=True,
                    )
                    bevel_edges = get_bevel_edges(plate)
                    delete(plate)
                    plate = butil.spawn_cube()
                    butil.modify_mesh(
                        plate,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="plate"),
                        ng_inputs=self.params,
                        apply=True,
                    )
                    plate = add_bevel(plate, bevel_edges)
                except:
                    plate = butil.spawn_cube()
                    butil.modify_mesh(
                        plate,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="plate"),
                        ng_inputs=self.params,
                        apply=True,
                    )
                save_obj_parts_add([plate], self.ps['path'], self.ps['i'], "plate", first=False, use_bpy=True, parent_obj_id=parent_id, joint_info=joint_info, material=material)
            else:
                material = None#[[self.shaders['Surface_'], "Out"], [self.shaders['BlackGlass_'], "In"]]
                parent_id = "world"
                joint_info = {
                    "name": get_joint_name("fixed"),
                    "type": "fixed",
                }
                try:
                    panel = butil.spawn_cube()
                    butil.modify_mesh(
                        panel,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="panel", preprocess=True),
                        ng_inputs=self.params,
                        apply=True,
                    )
                    bevel_edges = get_bevel_edges(panel)
                    delete(panel)
                    panel = butil.spawn_cube()
                    butil.modify_mesh(
                        panel,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="panel"),
                        ng_inputs=self.params,
                        apply=True,
                    )
                    panel = add_bevel(panel, bevel_edges)
                    panel_co = read_co(panel)
                    rotate = butil.spawn_cylinder(radius=self.params['PanelWidth'] / 6, depth=self.params['PanelWidth'] / 18)
                    rotate.rotation_euler[1] = np.pi / 2
                    indicator = butil.spawn_cube()
                    indicator.scale = (self.params['PanelWidth'] / 36, self.params['PanelWidth'] / 36, self.params['PanelWidth'] / 6 - self.params['PanelWidth'] / 36)
                    butil.apply_transform(indicator, True)
                    indicator.location = (self.params['Depth'] + self.params['DoorThickness'] + self.params['PanelWidth'] / 18, (co_text[:, 1].min() + co_text[:, 1].max()) / 2, self.params['Height'] * 0.4 + self.params['PanelWidth'] / 18)
                    butil.apply_transform(indicator, True)
                    butil.apply_transform(rotate, True)
                    rotate.location = (self.params['Depth'] + self.params['DoorThickness'], (co_text[:, 1].min() + co_text[:, 1].max()) / 2, self.params['Height'] * 0.4)
                    butil.apply_transform(rotate, True)
                    butil.select_none()
                    rotate.select_set(True)
                    bpy.context.view_layer.objects.active = rotate
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.bevel(
                        offset=self.params['PanelWidth'] / 36 / 2 /8, offset_pct=0, segments=8, release_confirm=True, face_strength_mode="ALL"
                    )
                    bpy.ops.object.mode_set(mode='OBJECT')
                    butil.select_none()
                    indicator.select_set(True)
                    bpy.context.view_layer.objects.active = indicator
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.bevel(
                        offset=self.params['PanelWidth'] / 36*0.95, offset_pct=0, segments=8, release_confirm=True, face_strength_mode="ALL"
                    )
                    bpy.ops.object.mode_set(mode='OBJECT')
                    self.shaders['Rotate_'].apply(rotate, rough=True)
                    button_width = (panel_co[:, 1].max() - panel_co[:, 1].min()) / 7
                    button_height = self.params['PanelWidth'] / 12 * (1 - self.button_lines * 0.1)
                    gap = button_width
                    rotate.location[2] += self.button_lines * (button_height)
                    indicator.location[2] += self.button_lines * (button_height)
                    butil.apply_transform(rotate, True)
                    butil.apply_transform(rotate, True)
                    butil.apply_transform(indicator, True)
                    butil.select_none()
                    indicator.select_set(True)
                    bpy.ops.object.modifier_add(type='SMOOTH')
                    bpy.context.object.modifiers["Smooth"].factor = 1
                    bpy.context.object.modifiers["Smooth"].iterations = 100
                    bpy.ops.object.modifier_apply(modifier="Smooth")
                    buttons = []
                    use_aux_button = np.random.choice([True, False], p=[0.9, 0.1])
                    use_aux_button = True
                    
                    if use_aux_button:
                        all_same = np.random.choice([True, False], p=[0.5, 0.5])
                    #all_same = False
                    aux_button = None
                    for i in range(self.button_lines):
                        for j in range(3):
                            button = butil.spawn_cube()
                            button.scale = (button_height / 4, button_width, button_height)
                            button.location = (self.params['Depth'] + self.params['DoorThickness'], panel_co[:, 1].min() + j * (button_width) + (j)* gap+ button_width * 1.5, self.params['Height'] * 0.15 + i * (button_height) * 1.3)
                            butil.apply_transform(button, True)
                            bpy.context.view_layer.objects.active = button
                            bpy.ops.object.mode_set(mode='EDIT')
                            bpy.ops.mesh.bevel(
                                offset=button_height / 8, offset_pct=0, segments=8, release_confirm=True, face_strength_mode="ALL"
                            )
                            bpy.ops.object.mode_set(mode='OBJECT')
                            butil.apply_transform(button, True)
                            new_btn = False
                            if use_aux_button:
                                if not all_same:
                                    new_btn = True
                                    aux_button = butil.deep_clone_obj(random_auxiliary('buttons')[0], keep_materials=False, keep_modifiers=False)
                                elif aux_button is None:
                                    new_btn = True
                                    aux_button = butil.deep_clone_obj(random_auxiliary('buttons')[0], keep_materials=False, keep_modifiers=False)
                                #aux_button = aux_button[0]
                                if new_btn:
                                    aux_button.rotation_euler = np.pi / 2, 0, np.pi / 2
                                    butil.apply_transform(aux_button, True)
                                    co = read_co(button)
                                    co_ = read_co(aux_button)
                                    scale = co[:, 0].max() - co[:, 0].min(), co[:, 1].max() - co[:, 1].min(), co[:, 2].max() - co[:, 2].min()
                                    scale_t = co_[:, 0].max() - co_[:, 0].min(), co_[:, 1].max() - co_[:, 1].min(), co_[:, 2].max() - co_[:, 2].min()
                                    s = scale[0] / scale_t[0], scale[1] / scale_t[1], scale[2] / scale_t[2] 
                                    aux_button.scale = s
                                    butil.apply_transform(aux_button, True)
                                    aux_button.location = (self.params['Depth'] + self.params['DoorThickness'], panel_co[:, 1].min() + j * (button_width) + (j)* gap+ button_width * 1.5, self.params['Height'] * 0.15 + i * (button_height) * 1.3)
                                    butil.apply_transform(aux_button, True)
                                    button = aux_button
                            self.shaders['Rotate_'].apply(button, rough=True)

                            save_obj_parts_add([butil.deep_clone_obj(button, keep_materials=True, keep_modifiers=True)], self.ps['path'], self.ps['i'], "button", first=False, use_bpy=True, parent_obj_id="world", joint_info={
                                "name": get_joint_name("prismatic"),
                                "type": "prismatic",
                                "axis": (1, 0, 0),
                                "limit": {
                                    "lower": -button_height / 8,
                                    "upper": 0,
                                },
                            }, material=material)
                    rotate = butil.join_objects([rotate, indicator])
                    if self.use_aux_botton:
                        botton = butil.deep_clone_obj(self.aux_botton[0], keep_materials=False, keep_modifiers=False)
                        botton.rotation_euler = (np.pi / 2, 0, np.pi / 2)
                        butil.apply_transform(botton, True)
                        co_b = read_co(rotate)
                        scale = co_b[:, 0].max() - co_b[:, 0].min(), co_b[:, 1].max() - co_b[:, 1].min(), co_b[:, 2].max() - co_b[:, 2].min()
                        botton.scale = scale
                        butil.apply_transform(botton, True)
                        botton.location = (co_b[:, 0].min() + scale[0] / 2, co_b[:, 1].min() + scale[1] / 2, co_b[:, 2].min() + scale[2] / 2)
                        butil.apply_transform(botton, True)
                        rotate = botton
                        self.shaders['Rotate_'].apply(rotate, rough=random.choice([True, False]))

                    res = save_obj_parts_add([rotate], self.ps['path'], self.ps['i'], "botton", first=False, use_bpy=True, parent_obj_id=parent_id, joint_info={
                        "name": get_joint_name("continuous"),
                        "type": "continuous",
                        "axis": (1, 0, 0),
                    })
                    # save_obj_parts_add([indicator], self.ps['path'], self.ps['i'], "indicator", first=False, use_bpy=True, parent_obj_id=res[0], joint_info={
                    #     "name": get_joint_name("fixed"),
                    #     "type": "fixed",
                    # })

                except Exception as e:
                    print(e)
                    panel = butil.spawn_cube()
                    butil.modify_mesh(
                        panel,
                        "NODES",
                        node_group=nodegroup_microwave_geometry(return_type_name="panel"),
                        ng_inputs=self.params,
                        apply=True,
                    )
                #.location[0] += 0.02
                butil.apply_transform(panel, True)
                use_surface = np.random.choice([True, False])
                if use_surface:
                    panel = butil.deep_clone_obj(panel, keep_materials=False)
                    material = [self.shaders['Surface_']]
                save_obj_parts_add([panel], self.ps['path'], self.ps['i'], "panel", first=False, use_bpy=True, parent_obj_id=parent_id, joint_info=joint_info, material=material)
            #res = node_utils.save_geometry_new(assets, "part", i, self.params['i'], self.params['path'], first, True, material=material, parent_obj_id=parent_id, joint_info=joint_info)
            #if res:
                #first = False
        node_utils.save_geometry_new(assets, "whole", 0, self.ps['i'], self.ps['path'], False, True)
        save_obj_parts_add([assets], self.ps['path'], self.ps['i'], "part", first=False, use_bpy=True)
        
        return assets
            


@node_utils.to_nodegroup("nodegroup_plate", singleton=False, type="GeometryNodeTree")
def nodegroup_plate(nw: NodeWrangler):
    # Code generated using version 2.6.5 of the node_transpiler

    curve_circle = nw.new_node(Nodes.CurveCircle, input_kwargs={"Resolution": 128})

    bezier_segment = nw.new_node(
        Nodes.CurveBezierSegment,
        input_kwargs={
            "Start Handle": (0.0000, 0.0000, 0.0000),
            "End": (1.0000, 0.0000, 0.4000),
        },
    )

    transform = nw.new_node(
        Nodes.Transform,
        input_kwargs={"Geometry": bezier_segment, "Rotation": (1.5708, 0.0000, 0.0000)},
    )

    curve_to_mesh = nw.new_node(
        Nodes.CurveToMesh,
        input_kwargs={
            "Curve": curve_circle.outputs["Curve"],
            "Profile Curve": transform,
        },
    )

    group_input = nw.new_node(
        Nodes.GroupInput,
        expose_input=[("NodeSocketVectorXYZ", "Scale", (1.0000, 1.0000, 1.0000))],
    )

    transform_1 = nw.new_node(
        Nodes.Transform,
        input_kwargs={"Geometry": curve_to_mesh, "Scale": group_input.outputs["Scale"]},
    )

    group_output = nw.new_node(
        Nodes.GroupOutput,
        input_kwargs={"Mesh": transform_1},
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
            ("NodeSocketInt", "Resolution", 10),
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
    "nodegroup_microwave_geometry", singleton=False, type="GeometryNodeTree"
)
def nodegroup_microwave_geometry(nw: NodeWrangler, preprocess: bool = False, return_type_name=""):
    # Code generated using version 2.6.5 of the node_transpiler

    group_input = nw.new_node(
        Nodes.GroupInput,
        expose_input=[
            ("NodeSocketFloat", "Depth", 0.0000),
            ("NodeSocketFloat", "Width", 0.0000),
            ("NodeSocketFloat", "Height", 0.0000),
            ("NodeSocketFloat", "PanelWidth", 0.5000),
            ("NodeSocketFloat", "MarginZ", 0.0000),
            ("NodeSocketFloat", "DoorThickness", 0.0000),
            ("NodeSocketFloat", "DoorMargin", 0.0500),
            ("NodeSocketFloat", "DoorRotation", 0.0000),
            ("NodeSocketString", "BrandName", "BrandName"),
            ("NodeSocketMaterial", "Surface", None),
            ("NodeSocketMaterial", "Back", None),
            ("NodeSocketMaterial", "BlackGlass", None),
            ("NodeSocketMaterial", "Glass", None),
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

    cube = nw.new_node(nodegroup_cube().name, input_kwargs={"Size": combine_xyz})

    subtract = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: group_input.outputs["Width"],
            1: group_input.outputs["PanelWidth"],
        },
        attrs={"operation": "SUBTRACT"},
    )

    subtract_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: group_input.outputs["Height"],
            1: group_input.outputs["MarginZ"],
        },
        attrs={"operation": "SUBTRACT"},
    )

    combine_xyz_1 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={
            "X": group_input.outputs["Depth"],
            "Y": subtract,
            "Z": subtract_1,
        },
    )

    scale = nw.new_node(
        Nodes.VectorMath,
        input_kwargs={0: group_input.outputs["MarginZ"], "Scale": 0.5000},
        attrs={"operation": "SCALE"},
    )

    cube_1 = nw.new_node(
        nodegroup_cube().name,
        input_kwargs={"Size": combine_xyz_1, "Pos": scale.outputs["Vector"]},
    )

    difference = nw.new_node(
        Nodes.MeshBoolean, input_kwargs={"Mesh 1": cube, "Mesh 2": cube_1}
    )

    cube_2 = nw.new_node(
        nodegroup_cube().name,
        input_kwargs={
            "Size": (0.0300, 0.0300, 0.0100),
            "Pos": (0.1000, 0.0000, 0.0500),
            "Resolution": 2,
        },
    )

    geometry_to_instance_1 = nw.new_node(
        "GeometryNodeGeometryToInstance", input_kwargs={"Geometry": cube_2}
    )

    duplicate_elements = nw.new_node(
        Nodes.DuplicateElements,
        input_kwargs={"Geometry": geometry_to_instance_1, "Amount": 10},
        attrs={"domain": "INSTANCE"},
    )

    multiply = nw.new_node(
        Nodes.Math,
        input_kwargs={0: duplicate_elements.outputs["Duplicate Index"], 1: 0.0400},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_7 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"X": multiply})

    set_position_1 = nw.new_node(
        Nodes.SetPosition,
        input_kwargs={
            "Geometry": duplicate_elements.outputs["Geometry"],
            "Offset": combine_xyz_7,
        },
    )

    duplicate_elements_1 = nw.new_node(
        Nodes.DuplicateElements,
        input_kwargs={"Geometry": set_position_1, "Amount": 7},
        attrs={"domain": "INSTANCE"},
    )

    multiply_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: duplicate_elements_1.outputs["Duplicate Index"], 1: 0.0200},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_8 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"Z": multiply_1})

    set_position_2 = nw.new_node(
        Nodes.SetPosition,
        input_kwargs={
            "Geometry": duplicate_elements_1.outputs["Geometry"],
            "Offset": combine_xyz_8,
        },
    )

    difference_1 = nw.new_node(
        Nodes.MeshBoolean,
        input_kwargs={
            "Mesh 1": difference.outputs["Mesh"],
            "Mesh 2": [duplicate_elements_1.outputs["Geometry"], set_position_2],
        },
    )

    set_material_1 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": difference_1.outputs["Mesh"],
            "Material": group_input.outputs["Back"],
        },
    )

    combine_xyz_2 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={
            "X": group_input.outputs["DoorThickness"],
            "Y": group_input.outputs["Width"],
            "Z": group_input.outputs["Height"],
        },
    )

    combine_xyz_3 = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"X": group_input.outputs["Depth"]}
    )

    cube_3 = nw.new_node(
        nodegroup_cube().name,
        input_kwargs={"Size": combine_xyz_2, "Pos": combine_xyz_3, "Resolution": 10},
    )

    position = nw.new_node(Nodes.InputPosition)

    separate_xyz = nw.new_node(Nodes.SeparateXYZ, input_kwargs={"Vector": position})

    subtract_2 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: group_input.outputs["Width"],
            1: group_input.outputs["PanelWidth"],
        },
        attrs={"operation": "SUBTRACT"},
    )

    multiply_2 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["MarginZ"]},
        attrs={"operation": "MULTIPLY"},
    )

    add = nw.new_node(Nodes.Math, input_kwargs={0: subtract_2, 1: multiply_2})

    less_than = nw.new_node(
        Nodes.Math,
        input_kwargs={0: separate_xyz.outputs["Y"], 1: add},
        attrs={"operation": "LESS_THAN"},
    )

    separate_geometry = nw.new_node(
        Nodes.SeparateGeometry,
        input_kwargs={"Geometry": cube_3, "Selection": less_than},
        attrs={"domain": "FACE"},
    )

    convex_hull = nw.new_node(
        Nodes.ConvexHull,
        input_kwargs={"Geometry": separate_geometry.outputs["Selection"]},
    )

    subdivide_mesh = nw.new_node(
        Nodes.SubdivideMesh, input_kwargs={"Mesh": convex_hull, "Level": 0}
    )

    position_1 = nw.new_node(Nodes.InputPosition)

    center = nw.new_node(
        nodegroup_center().name,
        input_kwargs={
            "Geometry": subdivide_mesh,
            "Vector": position_1,
            "MarginX": -1.0000,
            "MarginZ": group_input.outputs["DoorMargin"],
        },
    )

    set_material_3 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": subdivide_mesh,
            "Selection": center.outputs["In"],
            "Material": group_input.outputs["BlackGlass"],
        },
    )

    set_material_2 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": set_material_3,
            "Selection": center.outputs["Out"],
            "Material": group_input.outputs["Surface"],
        },
    )

    add_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: group_input.outputs["Depth"],
            1: group_input.outputs["DoorThickness"],
        },
    )

    bounding_box_1 = nw.new_node(
        Nodes.BoundingBox, input_kwargs={"Geometry": subdivide_mesh}
    )

    add_2 = nw.new_node(
        Nodes.VectorMath,
        input_kwargs={
            0: bounding_box_1.outputs["Min"],
            1: bounding_box_1.outputs["Max"],
        },
    )

    scale_1 = nw.new_node(
        Nodes.VectorMath,
        input_kwargs={0: add_2.outputs["Vector"], "Scale": 0.5000},
        attrs={"operation": "SCALE"},
    )

    separate_xyz_3 = nw.new_node(
        Nodes.SeparateXYZ, input_kwargs={"Vector": scale_1.outputs["Vector"]}
    )

    separate_xyz_4 = nw.new_node(
        Nodes.SeparateXYZ, input_kwargs={"Vector": bounding_box_1.outputs["Min"]}
    )

    add_3 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: separate_xyz_4.outputs["Z"],
            1: group_input.outputs["DoorMargin"],
        },
    )

    combine_xyz_5 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={"X": add_1, "Y": separate_xyz_3.outputs["Y"], "Z": add_3},
    )

    text = nw.new_node(
        nodegroup_text().name,
        input_kwargs={
            "Translation": combine_xyz_5,
            "String": group_input.outputs["BrandName"],
            "Size": 0.0300,
            "Offset Scale": 0.0020,
        },
    )

    text = complete_no_bevel(nw, text, preprocess)

    join_geometry_1 = nw.new_node(
        Nodes.JoinGeometry, input_kwargs={"Geometry": [set_material_2, text]}
    )

    geometry_to_instance = nw.new_node(
        "GeometryNodeGeometryToInstance", input_kwargs={"Geometry": join_geometry_1}
    )

    z = nw.scalar_multiply(
        group_input.outputs["DoorRotation"], 1 if not preprocess else 0
    )

    combine_xyz_6 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"Z": z})

    rotate_instances = nw.new_node(
        Nodes.RotateInstances,
        input_kwargs={
            "Instances": geometry_to_instance,
            "Rotation": combine_xyz_6,
            "Pivot Point": combine_xyz_3,
        },
    )

    plate = nw.new_node(
        nodegroup_plate().name, input_kwargs={"Scale": (0.1000, 0.1000, 0.1000)}
    )

    multiply_add = nw.new_node(
        Nodes.VectorMath,
        input_kwargs={
            0: combine_xyz_1,
            1: (0.5000, 0.5000, 0.0000),
            2: scale.outputs["Vector"],
        },
        attrs={"operation": "MULTIPLY_ADD"},
    )

    set_position = nw.new_node(
        Nodes.SetPosition,
        input_kwargs={"Geometry": plate, "Offset": multiply_add.outputs["Vector"]},
    )

    set_material = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": set_position,
            "Material": group_input.outputs["Glass"],
        },
    )

    convex_hull_1 = nw.new_node(
        Nodes.ConvexHull,
        input_kwargs={"Geometry": separate_geometry.outputs["Inverted"]},
    )

    subdivide_mesh_1 = nw.new_node(
        Nodes.SubdivideMesh, input_kwargs={"Mesh": convex_hull_1, "Level": 0}
    )

    position_2 = nw.new_node(Nodes.InputPosition)

    center_1 = nw.new_node(
        nodegroup_center().name,
        input_kwargs={
            "Geometry": subdivide_mesh_1,
            "Vector": position_2,
            "MarginX": -1.0000,
            "MarginY": 0.0010,
            "MarginZ": group_input.outputs["DoorMargin"],
        },
    )

    set_material_4 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": subdivide_mesh_1,
            "Selection": center_1.outputs["In"],
            "Material": group_input.outputs["BlackGlass"],
        },
    )

    set_material_5 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": set_material_4,
            "Selection": center_1.outputs["Out"],
            "Material": group_input.outputs["Surface"],
        },
    )

    add_4 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: group_input.outputs["Depth"],
            1: group_input.outputs["DoorThickness"],
        },
    )

    bounding_box = nw.new_node(
        Nodes.BoundingBox, input_kwargs={"Geometry": subdivide_mesh_1}
    )

    add_5 = nw.new_node(
        Nodes.VectorMath,
        input_kwargs={0: bounding_box.outputs["Min"], 1: bounding_box.outputs["Max"]},
    )

    scale_2 = nw.new_node(
        Nodes.VectorMath,
        input_kwargs={0: add_5.outputs["Vector"], "Scale": 0.5000},
        attrs={"operation": "SCALE"},
    )

    separate_xyz_1 = nw.new_node(
        Nodes.SeparateXYZ, input_kwargs={"Vector": scale_2.outputs["Vector"]}
    )

    separate_xyz_2 = nw.new_node(
        Nodes.SeparateXYZ, input_kwargs={"Vector": bounding_box.outputs["Max"]}
    )

    subtract_3 = nw.new_node(
        Nodes.Math,
        input_kwargs={
            0: separate_xyz_2.outputs["Z"],
            1: group_input.outputs["DoorMargin"],
        },
        attrs={"operation": "SUBTRACT"},
    )

    add_6 = nw.new_node(Nodes.Math, input_kwargs={0: subtract_3, 1: -0.0500})

    combine_xyz_4 = nw.new_node(
        Nodes.CombineXYZ,
        input_kwargs={"X": add_4, "Y": separate_xyz_1.outputs["Y"], "Z": add_6},
    )

    text_1 = nw.new_node(
        nodegroup_text().name,
        input_kwargs={
            "Translation": combine_xyz_4,
            "String": "12:01",
            "Offset Scale": 0.0050,
        },
    )

    text_1 = complete_no_bevel(nw, text_1, preprocess)

    store_1 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={"Geometry": text_1, "Name": "part", "Value": 1},
    )

    if return_type_name == "text":
        store_1 = nw.new_node(
            Nodes.RealizeInstances, [store_1]
        )
        group_output = nw.new_node(
            Nodes.GroupOutput,
            input_kwargs={"Geometry": store_1},
            attrs={"is_active_output": True},
        )
        return 

    store_2 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={"Geometry": set_material_1, "Name": "part", "Value": 2},
    )

    if return_type_name == "body":
        store_2 = nw.new_node(
            Nodes.RealizeInstances, [store_2]
        )

        group_output = nw.new_node(
            Nodes.GroupOutput,
            input_kwargs={"Geometry": store_2},
            attrs={"is_active_output": True},
        )
        return 

    store_3 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={"Geometry": rotate_instances, "Name": "part", "Value": 3},
    )

    if return_type_name == "door":
        store_3 = nw.new_node(
            Nodes.RealizeInstances, [store_3]
        )
        group_output = nw.new_node(
            Nodes.GroupOutput,
            input_kwargs={"Geometry": store_3},
            attrs={"is_active_output": True},
        )
        return 

    store_4 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={"Geometry": set_material, "Name": "part", "Value": 4},
    )

    if return_type_name == "plate":
        store_4 = nw.new_node(
            Nodes.RealizeInstances, [store_4]
        )
        group_output = nw.new_node(
            Nodes.GroupOutput,
            input_kwargs={"Geometry": store_4},
            attrs={"is_active_output": True},
        )
        return 

    store_5 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={"Geometry": set_material_5, "Name": "part", "Value": 5},
    )

    if return_type_name == "panel":
        store_5 = nw.new_node(
            Nodes.RealizeInstances, [store_5]
        )
        group_output = nw.new_node(
            Nodes.GroupOutput,
            input_kwargs={"Geometry": store_5},
            attrs={"is_active_output": True},
        )
        return 

    join_geometry = nw.new_node(
        Nodes.JoinGeometry,
        input_kwargs={
            "Geometry": [
store_1, 
store_2,
store_3,
store_4,
store_5,
            ]
        },
    )
    geometry = nw.new_node(Nodes.RealizeInstances, [join_geometry])
    group_output = nw.new_node(
        Nodes.GroupOutput,
        input_kwargs={"Geometry": geometry},
        attrs={"is_active_output": True},
    )
