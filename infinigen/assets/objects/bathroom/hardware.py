# Copyright (C) 2024, Princeton University.
# This source code is licensed under the BSD 3-Clause license found in the LICENSE file in the root directory of this source tree.

# Authors: Lingjie Mei

import bpy
import numpy as np
from numpy.random import uniform

from infinigen.assets.material_assignments import AssetList
from infinigen.assets.utils.decorate import subsurf
from infinigen.assets.utils.object import (
    join_objects,
    new_base_cylinder,
    new_cube,
    join_objects_save_whole,
    save_obj_parts_add,
    get_joint_name
)

# save_objects_obj,
from infinigen.core.placement.factory import AssetFactory
from infinigen.core.util import blender as butil
from infinigen.core.util.math import FixedSeed
from infinigen.core.util.random import log_uniform
import math


class HardwareFactory(AssetFactory):
    def __init__(self, factory_seed, coarse=False):
        super(HardwareFactory, self).__init__(factory_seed, coarse)
        with FixedSeed(self.factory_seed):
            self.attachment_radius = uniform(0.02, 0.03)
            self.attachment_depth = uniform(0.01, 0.015)
            self.radius = uniform(0.01, 0.015)
            self.depth = uniform(0.06, 0.1)
            self.is_circular = uniform() < 0.5
            self.hardware_type = np.random.choice(["hook", "holder", "bar", "ring"])
            self.hook_length = self.attachment_radius * uniform(2, 4)
            self.holder_length = uniform(0.15, 0.25)
            self.bar_length = uniform(0.4, 0.8)
            self.extension_length = self.attachment_radius * uniform(2, 3)
            self.ring_radius = log_uniform(2, 6) * self.attachment_radius

            material_assignments = AssetList["HardwareFactory"]()
            self.surface = material_assignments["surface"].assign_material()
            is_scratch = uniform() < material_assignments["wear_tear_prob"][0]
            is_edge_wear = uniform() < material_assignments["wear_tear_prob"][1]
            self.scratch = material_assignments["wear_tear"][0] if is_scratch else None
            self.edge_wear = (
                material_assignments["wear_tear"][1] if is_edge_wear else None
            )
    def make_attachment(self, translation=None):
        base = new_base_cylinder() if self.is_circular else new_cube()
        base.scale = (
            self.attachment_radius,
            self.attachment_radius,
            self.attachment_depth / 2,
        )
        base.rotation_euler[0] = np.pi / 2
        base.location[1] = -self.attachment_depth / 2
        butil.apply_transform(base, True)
        self.finalize_assets(base)
        if translation is not None:
            base.location = translation
            butil.apply_transform(base, True)
        joint_info = {
            "type": "continuous_prismatic",
            "name": get_joint_name("continuous_prismatic"),
            "axis": (0, 1, 0),
            "axis_1": (0, 1, 0),
            "limit":{
                "lower_1": -self.depth / 2,
                "upper_1": 0
            }
        }
        

        save_obj_parts_add(base, self.params.get("path", None), self.params.get("i", None), "hardware_base", first=False, use_bpy=True, parent_obj_id="world", joint_info=joint_info)

        rod = new_base_cylinder() if self.is_circular else new_cube()
        rod.scale = self.radius, self.radius, self.depth / 2
        rod.rotation_euler[0] = np.pi / 2
        rod.location[1] = -self.depth / 2
        butil.apply_transform(rod, True)
        self.finalize_assets(rod)
        if translation is not None:
            rod.location = translation
            butil.apply_transform(rod, True)
        if self.hardware_type != "bar" and self.hardware_type != "holder":
            joint_info = {
                "type": "continuous",
                "name": get_joint_name("continuous"),
                "axis": (0, 1, 0)  
            }
        else:
            joint_info = {
                "type": "fixed",
                "name": get_joint_name("fixed"),
            }
        
        save_obj_parts_add(rod, self.params.get("path", None), self.params.get("i", None), "rod", first=False, use_bpy=True, parent_obj_id="world", joint_info=joint_info)
        
        obj = join_objects([base, rod])
        return obj

    def make_hook(self):
        obj = new_base_cylinder() if self.is_circular else new_cube()
        obj.scale = self.radius, self.radius, self.hook_length / 2
        butil.apply_transform(obj)
        obj.location[1] = -self.depth
        obj.scale = [1 + 1e-3] * 3
        butil.apply_transform(obj, True)
        self.finalize_assets(obj)
        save_obj_parts_add(obj, self.params.get("path", None), self.params.get("i", None), "hook", first=True, use_bpy=True, parent_obj_id=2, joint_info={
            "type": "fixed",
            "name": get_joint_name("fixed"),
        })
        return obj

    def make_holder(self):
        obj = new_base_cylinder() if self.is_circular else new_cube()
        obj.scale = (
            self.radius,
            self.radius,
            (self.holder_length + self.extension_length) / 2,
        )
        obj.rotation_euler[1] = np.pi / 2
        obj.location[0] = (self.holder_length - self.extension_length) / 2
        butil.apply_transform(obj, True)
        obj.location[1] = -self.depth
        obj.scale = [1 + 1e-3] * 3
        butil.apply_transform(obj, True)
        self.finalize_assets(obj)
        save_obj_parts_add(obj, self.params.get("path", None), self.params.get("i", None), "holder", first=True, use_bpy=True, parent_obj_id=2, joint_info={
            "type": "fixed",
            "name": get_joint_name("fixed"),
        })
        return obj

    def make_bar(self):
        obj = new_base_cylinder() if self.is_circular else new_cube()
        obj.scale = (
            self.radius,
            self.radius,
            self.bar_length / 2 + self.extension_length,
        )
        obj.rotation_euler[1] = np.pi / 2
        obj.location[0] = self.bar_length / 2
        butil.apply_transform(obj, True)
        obj.location[1] = -self.depth
        obj.scale = [1 + 1e-3] * 3
        butil.apply_transform(obj, True)
        self.finalize_assets(obj)
        save_obj_parts_add(obj, self.params.get("path", None), self.params.get("i", None), "bar", first=True, use_bpy=True, parent_obj_id=2, joint_info={
            "type": "fixed",
            "name": get_joint_name("fixed"),
        })
        return obj

    def make_ring(self):
        bpy.ops.mesh.primitive_torus_add(
            major_segments=128,
            major_radius=self.ring_radius,
            minor_radius=self.radius * uniform(0.4, 0.7),
        )
        obj = bpy.context.active_object
        obj.rotation_euler[0] = np.pi / 2
        obj.location = 0, self.attachment_depth, -self.ring_radius
        butil.apply_transform(obj, True)
        subsurf(obj, 2)
        obj.location[1] = -self.depth
        obj.scale = [1 + 1e-3] * 3
        butil.apply_transform(obj, True)
        self.finalize_assets(obj)
        save_obj_parts_add(obj, self.params.get("path", None), self.params.get("i", None), "ring", first=True, use_bpy=True, parent_obj_id=2, joint_info={
            "type": "flip_revolute",
            "name": get_joint_name("flip_revolute"),
            "axis": (1, 0, 0),
            "axis_1": (0, 1, 0),
            "limit": {
                "lower": -math.pi,
                "upper": 0,
                "lower_1": -math.pi,
                "upper_1": math.pi
            },
            "origin_shift": (0, 0, self.ring_radius)
        })

        return obj

    def create_asset(self, **params) -> bpy.types.Object:
        self.params = params
        match self.hardware_type:
            case "hook":
                extra = self.make_hook()
            case "holder":
                extra = self.make_holder()
            case "bar":
                extra = self.make_bar()
            case "ring":
                extra = self.make_ring()
            case _:
                return self.make_attachment()
        #extra.scale = [1 + 1e-3] * 3
        # extra.location[1] = -self.depth
        # butil.apply_transform(extra, True)
        parts = [self.make_attachment(), extra]
        if self.hardware_type == "bar":
            attachment_ = self.make_attachment(translation=(self.bar_length, 0, 0))
            #attachment_.location[0] = self.bar_length
            #butil.apply_transform(attachment_, True)
            parts.append(attachment_)
        obj = join_objects(parts)
        #obj.rotation_euler[-1] = np.pi / 2
        #butil.apply_transform(obj)
        join_objects_save_whole(obj, self.params.get("path", None), self.params.get("i", None), use_bpy=True)
        return obj

    def finalize_assets(self, assets):
        self.surface.apply(assets, metal_color="plain")
        if self.scratch:
            self.scratch.apply(assets)
        if self.edge_wear:
            self.edge_wear.apply(assets)
