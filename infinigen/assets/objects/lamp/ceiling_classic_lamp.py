# Copyright (C) 2023, Princeton University.
# This source code is licensed under the BSD 3-Clause license found in the LICENSE file in the root directory of this source tree.

# Authors: Stamatis Alexandropoulos

from numpy.random import randint, uniform

from infinigen.assets.lighting.indoor_lights import PointLampFactory
from infinigen.assets.materials.ceiling_light_shaders import (
    shader_lamp_bulb_nonemissive,
)
from infinigen.core import surface, tagging
from infinigen.core.nodes import node_utils
from infinigen.core.nodes.node_utils import save_geometry
from infinigen.core.nodes.node_wrangler import Nodes, NodeWrangler
from infinigen.core.placement.factory import AssetFactory
from infinigen.core.util import blender as butil
from infinigen.core.util.color import color_category
from infinigen.core.util.math import FixedSeed


def shader_lamp_material(nw: NodeWrangler):
    # Code generated using version 2.6.5 of the node_transpiler

    rgb = nw.new_node(Nodes.RGB)
    rgb.outputs[0].default_value = color_category("textile")

    principled_bsdf = nw.new_node(
        Nodes.PrincipledBSDF,
        input_kwargs={
            "Base Color": rgb,
            "Subsurface Radius": (0.1000, 0.1000, 0.1000),
            "Roughness": uniform(0.2, 0.9),
            "Sheen": 0.2068,
            "Clearcoat Roughness": 0.1436,
            "Transmission": 0.4045,
            "Transmission Roughness": 0.6932,
            "Emission": (0.9858, 0.9858, 0.9858, 1.0000),
            "Emission Strength": 0.0000,
            "Alpha": 0.8614,
        },
    )

    voronoi_texture = nw.new_node(
        Nodes.VoronoiTexture,
        input_kwargs={"Scale": 104.3000, "Randomness": 0.0000},
        attrs={"feature": "SMOOTH_F1"},
    )

    displacement = nw.new_node(
        Nodes.Displacement,
        input_kwargs={"Height": voronoi_texture.outputs["Distance"], "Scale": 0.4000},
    )

    material_output = nw.new_node(
        Nodes.MaterialOutput,
        input_kwargs={"Surface": principled_bsdf, "Displacement": displacement},
        attrs={"is_active_output": True},
    )


def shader_inside_medal(nw: NodeWrangler):
    # Code generated using version 2.6.5 of the node_transpiler

    principled_bsdf = nw.new_node(
        Nodes.PrincipledBSDF,
        input_kwargs={
            "Base Color": (0.0018, 0.0015, 0.0000, 1.0000),
            "Metallic": 1.0000,
            "Roughness": 0.0682,
        },
    )

    material_output = nw.new_node(
        Nodes.MaterialOutput,
        input_kwargs={"Surface": principled_bsdf},
        attrs={"is_active_output": True},
    )


def shader_cable(nw: NodeWrangler):
    # Code generated using version 2.6.5 of the node_transpiler

    principled_bsdf = nw.new_node(
        Nodes.PrincipledBSDF,
        input_kwargs={
            "Base Color": (0.0000, 0.0000, 0.0000, 1.0000),
            "Metallic": 1.0000,
            "Roughness": 0.4273,
        },
    )

    material_output = nw.new_node(
        Nodes.MaterialOutput,
        input_kwargs={"Surface": principled_bsdf},
        attrs={"is_active_output": True},
    )


@node_utils.to_modifier("geometry_nodes", singleton=False, type="GeometryNodeTree")
def geometry_nodes(nw: NodeWrangler, preprocess: bool = False, **kwargs):
    # Code generated using version 2.6.5 of the node_transpiler

    if "inputs" in kwargs.keys():
        group_input = nw.new_node(
            Nodes.GroupInput,
            expose_input=[
                ("NodeSocketFloat", "cable_length", kwargs["inputs"]["cable_length"]),
                ("NodeSocketFloat", "cable_radius", kwargs["inputs"]["cable_radius"]),
                ("NodeSocketFloat", "height", kwargs["inputs"]["height"]),
                ("NodeSocketFloat", "bottom_radius", kwargs["inputs"]["bottom_radius"]),
                ("NodeSocketFloat", "top_radius", kwargs["inputs"]["top_radius"]),
                ("NodeSocketFloat", "Thickness", kwargs["inputs"]["Thickness"]),
                ("NodeSocketFloatDistance", "Amount", kwargs["inputs"]["Amount"]),
            ],
        )
    else:
        group_input = nw.new_node(
            Nodes.GroupInput,
            expose_input=[
                ("NodeSocketFloat", "cable_length", 0.7000),
                ("NodeSocketFloat", "cable_radius", 0.0500),
                ("NodeSocketFloat", "height", 0.0000),
                ("NodeSocketFloat", "bottom_radius", 0.0000),
                ("NodeSocketFloat", "top_radius", 0.0000),
                ("NodeSocketFloat", "Thickness", 0.5000),
                ("NodeSocketFloatDistance", "Amount", 1.0000),
            ],
        )

    combine_xyz = nw.new_node(
        Nodes.CombineXYZ, input_kwargs={"Z": group_input.outputs["cable_length"]}
    )

    curve_line = nw.new_node(Nodes.CurveLine, input_kwargs={"End": combine_xyz})

    curve_circle = nw.new_node(
        Nodes.CurveCircle,
        input_kwargs={"Resolution": 87, "Radius": group_input.outputs["cable_radius"]},
    )

    curve_to_mesh = nw.new_node(
        Nodes.CurveToMesh,
        input_kwargs={
            "Curve": curve_line,
            "Profile Curve": curve_circle.outputs["Curve"],
        },
    )

    store_ceiling_classic_lamp_1 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": curve_to_mesh,
            "Name": "ceiling_classic_lamp",
            "Value": 1,
        },
        attrs={"domain": "POINT", "data_type": "INT"},
    )

    transform_geometry = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": store_ceiling_classic_lamp_1.outputs["Geometry"],
            "Scale": (1.0000, 1.0000, -1.0000),
        },
    )

    set_material = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": transform_geometry,
            "Material": surface.shaderfunc_to_material(shader_cable),
        },
    )

    curve_circle_3 = nw.new_node(
        Nodes.CurveCircle, input_kwargs={"Radius": group_input.outputs["top_radius"]}
    )

    multiply = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["height"], 1: -0.5000},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_4 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"Z": multiply})

    transform_geometry_4 = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": curve_circle_3.outputs["Curve"],
            "Translation": combine_xyz_4,
        },
    )

    curve_line_3 = nw.new_node(
        Nodes.CurveLine,
        input_kwargs={
            "Start": (-1.0000, 0.0000, 0.0000),
            "End": (1.0000, 0.0000, 0.0000),
        },
    )

    geometry_to_instance = nw.new_node(
        "GeometryNodeGeometryToInstance", input_kwargs={"Geometry": curve_line_3}
    )

    reroute = nw.new_node(
        Nodes.Reroute, input_kwargs={"Input": group_input.outputs["Amount"]}
    )

    duplicate_elements = nw.new_node(
        Nodes.DuplicateElements,
        input_kwargs={"Geometry": geometry_to_instance, "Amount": reroute},
        attrs={"domain": "INSTANCE"},
    )

    store_ceiling_classic_lamp_4 = nw.new_node(
        Nodes.StoreNamedAttribute,
        input_kwargs={
            "Geometry": duplicate_elements.outputs["Geometry"],
            "Name": "ceiling_classic_lamp",
            "Value": nw.new_node(
                node_type=Nodes.Math,
                input_kwargs={
                    0: duplicate_elements.outputs["Duplicate Index"],
                    1: 4,
                },
                attrs={"operation": "ADD"},
            ),
        },
        attrs={"domain": "INSTANCE", "data_type": "INT"},
    )

    realize_instances_1 = nw.new_node(
        Nodes.RealizeInstances,
        input_kwargs={"Geometry": store_ceiling_classic_lamp_4.outputs["Geometry"]},
    )

    endpoint_selection_1 = nw.new_node(
        Nodes.EndpointSelection, input_kwargs={"Start Size": 0}
    )

    divide = nw.new_node(
        Nodes.Math, input_kwargs={0: 1.0000, 1: reroute}, attrs={"operation": "DIVIDE"}
    )

    multiply_1 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: duplicate_elements.outputs["Duplicate Index"], 1: divide},
        attrs={"operation": "MULTIPLY"},
    )

    sample_curve = nw.new_node(
        Nodes.SampleCurve,
        input_kwargs={"Curves": transform_geometry_4, "Factor": multiply_1},
        attrs={"use_all_curves": True},
    )

    set_position = nw.new_node(
        Nodes.SetPosition,
        input_kwargs={
            "Geometry": realize_instances_1,
            "Selection": endpoint_selection_1,
            "Position": sample_curve.outputs["Position"],
        },
    )

    endpoint_selection_2 = nw.new_node(
        Nodes.EndpointSelection, input_kwargs={"End Size": 0}
    )

    multiply_add = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["Thickness"], 2: 0.0000},
        attrs={"operation": "MULTIPLY_ADD"},
    )

    curve_circle_4 = nw.new_node(
        Nodes.CurveCircle, input_kwargs={"Radius": multiply_add}
    )

    transform_geometry_5 = nw.new_node(
        Nodes.Transform, input_kwargs={"Geometry": curve_circle_4.outputs["Curve"]}
    )

    sample_curve_1 = nw.new_node(
        Nodes.SampleCurve,
        input_kwargs={"Curves": transform_geometry_5, "Factor": multiply_1},
        attrs={"use_all_curves": True},
    )

    set_position_1 = nw.new_node(
        Nodes.SetPosition,
        input_kwargs={
            "Geometry": set_position,
            "Selection": endpoint_selection_2,
            "Position": sample_curve_1.outputs["Position"],
        },
    )

    join_geometry_3 = nw.new_node(
        Nodes.JoinGeometry,
        input_kwargs={
            "Geometry": [transform_geometry_4, set_position_1, transform_geometry_5]
        },
    )

    curve_circle_5 = nw.new_node(
        Nodes.CurveCircle, input_kwargs={"Radius": group_input.outputs["Thickness"]}
    )

    curve_to_mesh_3 = nw.new_node(
        Nodes.CurveToMesh,
        input_kwargs={
            "Curve": join_geometry_3,
            "Profile Curve": curve_circle_5.outputs["Curve"],
            "Fill Caps": True,
        },
    )

    transform_geometry_6 = nw.new_node(
        Nodes.Transform, input_kwargs={"Geometry": curve_to_mesh_3}
    )

    set_material_1 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": transform_geometry_6,
            "Material": surface.shaderfunc_to_material(shader_inside_medal),
        },
    )

    multiply_2 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: -1.5000, 1: -0.1000},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_1 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"Z": multiply_2})

    subtract = nw.new_node(
        Nodes.Math,
        input_kwargs={0: group_input.outputs["height"], 1: 0.0000},
        attrs={"operation": "SUBTRACT"},
    )

    multiply_3 = nw.new_node(
        Nodes.Math, input_kwargs={1: -1.0000}, attrs={"operation": "MULTIPLY"}
    )

    multiply_4 = nw.new_node(
        Nodes.Math,
        input_kwargs={0: subtract, 1: multiply_3},
        attrs={"operation": "MULTIPLY"},
    )

    combine_xyz_2 = nw.new_node(Nodes.CombineXYZ, input_kwargs={"Z": multiply_4})

    curve_line_2 = nw.new_node(
        Nodes.CurveLine, input_kwargs={"Start": combine_xyz_1, "End": combine_xyz_2}
    )

    spline_parameter = nw.new_node(Nodes.SplineParameter)

    map_range = nw.new_node(
        Nodes.MapRange,
        input_kwargs={
            "Value": spline_parameter.outputs["Factor"],
            3: group_input.outputs["bottom_radius"],
            4: group_input.outputs["top_radius"],
        },
    )

    set_curve_radius = nw.new_node(
        Nodes.SetCurveRadius,
        input_kwargs={"Curve": curve_line_2, "Radius": map_range.outputs["Result"]},
    )

    curve_circle_2 = nw.new_node(Nodes.CurveCircle)

    curve_to_mesh_2 = nw.new_node(
        Nodes.CurveToMesh,
        input_kwargs={
            "Curve": set_curve_radius,
            "Profile Curve": curve_circle_2.outputs["Curve"],
        },
    )

    flip_faces = nw.new_node(Nodes.FlipFaces, input_kwargs={"Mesh": curve_to_mesh_2})

    extrude_mesh = nw.new_node(
        Nodes.ExtrudeMesh,
        input_kwargs={
            "Mesh": curve_to_mesh_2,
            "Offset Scale": 0.0050,
            "Individual": False,
        },
    )

    join_geometry = nw.new_node(
        Nodes.JoinGeometry,
        input_kwargs={"Geometry": [flip_faces, extrude_mesh.outputs["Mesh"]]},
    )

    # store_ceiling_classic_lamp_2 = nw.new_node(
    #     Nodes.StoreNamedAttribute,
    #     input_kwargs={
    #         "Geometry": join_geometry,
    #         "Name": "ceiling_classic_lamp",
    #         "Value": 2,
    #     },
    #     attrs={"domain": "POINT", "data_type": "INT"},
    # )

    transform_geometry_2 = nw.new_node(
        Nodes.Transform,
        input_kwargs={"Geometry": join_geometry},
    )

    set_material_2 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": transform_geometry_2,
            "Material": surface.shaderfunc_to_material(shader_lamp_material),
        },
    )

    join_geometry_1 = nw.new_node(
        Nodes.JoinGeometry, input_kwargs={"Geometry": [set_material_1, set_material_2]}
    )

    ico_sphere = nw.new_node(
        Nodes.MeshIcoSphere, input_kwargs={"Radius": 0.0500, "Subdivisions": 4}
    )

    # store_ceiling_classic_lamp_3 = nw.new_node(
    #     Nodes.StoreNamedAttribute,
    #     input_kwargs={
    #         "Geometry": ico_sphere.outputs["Mesh"],
    #         "Name": "ceiling_classic_lamp",
    #         "Value": 3,
    #     },
    #     attrs={"domain": "POINT", "data_type": "INT"},
    # )

    set_material_3 = nw.new_node(
        Nodes.SetMaterial,
        input_kwargs={
            "Geometry": ico_sphere.outputs["Mesh"],
            "Material": surface.shaderfunc_to_material(shader_lamp_bulb_nonemissive),
        },
    )

    join_geometry_2 = nw.new_node(
        Nodes.JoinGeometry,
        input_kwargs={"Geometry": [set_material, join_geometry_1, set_material_3]},
    )

    transform_geometry_3 = nw.new_node(
        Nodes.Transform,
        input_kwargs={
            "Geometry": join_geometry_2,
            "Rotation": (0.0000, 3.1416, 0.0000),
        },
    )

    names = ["ceiling_classic_lamp"]
    parts = [4]

    if not preprocess:
        first = True
        for i, name in enumerate(names):
            named_attribute = nw.new_node(
                node_type=Nodes.NamedAttribute,
                input_args=[name],
                attrs={"data_type": "INT"},
            )
            for j in range(0, parts[i] + 1):
                compare = nw.new_node(
                    node_type=Nodes.Compare,
                    input_kwargs={"A": named_attribute, "B": j},
                    attrs={"data_type": "INT", "operation": "EQUAL"},
                )
                separate_geometry = nw.new_node(
                    node_type=Nodes.SeparateGeometry,
                    input_kwargs={
                        "Geometry": transform_geometry_3.outputs["Geometry"],
                        "Selection": compare.outputs["Result"],
                    },
                )
                output_geometry = separate_geometry
                a = save_geometry(
                    nw,
                    output_geometry,
                    kwargs.get("path", None),
                    name,
                    kwargs.get("i", "unknown"),
                    first=first,
                )
                if a:
                    first = False
        save_geometry(
            nw,
            transform_geometry_3,
            kwargs.get("path", None),
            "whole",
            kwargs.get("i", "unknown"),
        )

    group_output = nw.new_node(
        Nodes.GroupOutput,
        input_kwargs={"Geometry": transform_geometry_3},
        attrs={"is_active_output": True},
    )


class CeilingClassicLampFactory(AssetFactory):
    def __init__(self, factory_seed):
        super(CeilingClassicLampFactory, self).__init__(factory_seed)
        with FixedSeed(factory_seed):
            self.params = {
                "cable_length": uniform(0.6, 0.710),
                "cable_radius": uniform(0.015, 0.02),
                "height": uniform(0.4, 0.710),
                "top_radius": uniform(0.05, 0.2),
                "bottom_radius": uniform(0.22, 0.35),
                "Thickness": uniform(0.002, 0.006),
                "Amount": randint(1, 8),
            }
            self.light_factory = PointLampFactory(factory_seed)

        # self.beveler = BevelSharp(mult=uniform(1, 3))

    def create_placeholder(self, i, **params):
        obj = butil.spawn_cube()
        params.update({"i": i, "obj": obj, "input": self.params, "path": params.get("path", None)})
        butil.modify_mesh(
            obj,
            "NODES",
            node_group=geometry_nodes(**params),
            ng_inputs=self.params,
            apply=True,
            mod=True,
        )
        tagging.tag_system.relabel_obj(obj)
        return obj

    def create_asset(self, i, placeholder, face_size, **_):
        obj = butil.deep_clone_obj(placeholder, keep_materials=True)
        light = self.light_factory.spawn_asset(i)
        butil.parent_to(light, obj)
        return obj
