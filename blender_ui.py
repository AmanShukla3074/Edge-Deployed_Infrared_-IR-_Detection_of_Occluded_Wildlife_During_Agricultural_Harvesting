import bpy
import os
import math

# ============================================================
# SAFETY: ENSURE OBJECT MODE
# ============================================================
if bpy.context.object and bpy.context.object.mode != 'OBJECT':
    bpy.ops.object.mode_set(mode='OBJECT')

# ============================================================
# FIND OBJECTS FROM YOUR SCENE
# ============================================================
soil = bpy.data.objects.get("SOIL_GROUND")
nilgai = bpy.data.objects.get("mesh_0")
grass_objects = []

for obj in bpy.context.scene.objects:
    if obj.type == 'MESH' and obj.name.startswith("Object_2"):
        grass_objects.append(obj)

if soil is None:
    raise RuntimeError("SOIL_GROUND not found.")
if nilgai is None:
    raise RuntimeError("mesh_0 not found.")

# ============================================================
# ADJUST THE GROUND SIZE
# ============================================================
soil.scale = (2.0, 2.0, 1.0) 

# ============================================================
# FIX GRASS ORIENTATION & ARRANGE IN GRID (WITH DUPLICATION)
# ============================================================
if len(grass_objects) > 0:
    bpy.ops.object.select_all(action='DESELECT')
    
    # 1. Keep the first grass as a template and delete the rest
    base_grass = grass_objects[0]
    for i in range(1, len(grass_objects)):
        try:
            bpy.data.objects.remove(grass_objects[i], do_unlink=True)
        except:
            pass
            
    base_grass.select_set(True)
    bpy.context.view_layer.objects.active = base_grass
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.select_all(action='DESELECT')
    
    # ==========================================
    # SET YOUR GRASS COUNT AND SPACING HERE
    # ==========================================
    grass_rows = 10       
    grass_columns = 10    
    spacing = 1.75 
    # ==========================================
    
    start_x = -((grass_columns - 1) * spacing) / 2
    start_y = -((grass_rows - 1) * spacing) / 2
    
    grass_objects = [base_grass] 
    
    for row in range(grass_rows):
        for col in range(grass_columns):
            if row == 0 and col == 0:
                current_grass = base_grass
            else:
                current_grass = base_grass.copy()
                bpy.context.collection.objects.link(current_grass)
                grass_objects.append(current_grass)
            
            new_x = start_x + (col * spacing)
            new_y = start_y + (row * spacing)
            
            current_grass.matrix_world.translation.x = new_x
            current_grass.matrix_world.translation.y = new_y
            current_grass.matrix_world.translation.z = 0.0
            
# ============================================================
# CREATE MATERIALS (THERMAL AND NATURAL)
# ============================================================
def create_material(name, color, roughness=0.8, is_thermal=True):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1)
        bsdf.inputs["Roughness"].default_value = roughness
        
        # Only add emission glow if it is a thermal material
        if is_thermal:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = (color[0], color[1], color[2], 1)
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 0.15
        else:
            if "Emission Strength" in bsdf.inputs:
                bsdf.inputs["Emission Strength"].default_value = 0.0
            
    return mat

# We still create these so the 2nd script can find them later
gray_animal = create_material("THERMAL_GRAY_ANIMAL", (0.95, 0.95, 0.95))
gray_grass = create_material("THERMAL_GRAY_GRASS", (0.22, 0.22, 0.22))
gray_soil = create_material("THERMAL_GRAY_SOIL", (0.10, 0.10, 0.10))

ironbow_animal = create_material("THERMAL_IRONBOW_ANIMAL", (1.0, 0.10, 0.01))
ironbow_grass = create_material("THERMAL_IRONBOW_GRASS", (0.01, 0.02, 0.20))
ironbow_soil = create_material("THERMAL_IRONBOW_SOIL", (0.02, 0.01, 0.08))

# Create Natural Colors for the GUI Preview
natural_grass = create_material("NATURAL_GRASS", (0.05, 0.25, 0.02), is_thermal=False)
natural_soil = create_material("NATURAL_SOIL", (0.15, 0.10, 0.05), is_thermal=False)

def assign_material(obj, material):
    if obj is None: return
    if len(obj.data.materials) == 0:
        obj.data.materials.append(material)
    else:
        obj.data.materials[0] = material

# ============================================================
# FIXED CAMERA
# ============================================================
camera = bpy.data.objects.get("THERMAL_FIXED_CAMERA")
if camera is None:
    camera_data = bpy.data.cameras.new("THERMAL_FIXED_CAMERA")
    camera = bpy.data.objects.new("THERMAL_FIXED_CAMERA", camera_data)
    bpy.context.collection.objects.link(camera)

camera.location = (8.5, -12.0, 2.5)
camera.rotation_euler = (math.radians(85), 0, math.radians(35))
camera.data.lens = 52
bpy.context.scene.camera = camera

# ============================================================
# FIXED LIGHT (CHANGED TO SUNLIGHT FOR NATURAL LOOK)
# ============================================================
light = bpy.data.objects.get("THERMAL_FIXED_LIGHT")
if light is None:
    light_data = bpy.data.lights.new("THERMAL_FIXED_LIGHT", type='SUN')
    light = bpy.data.objects.new("THERMAL_FIXED_LIGHT", light_data)
    bpy.context.collection.objects.link(light)

# Configure as a Sun so it lights the whole environment evenly
light.data.type = 'SUN'
light.data.energy = 2.5
light.data.angle = math.radians(11)
light.rotation_euler = (math.radians(45), math.radians(30), math.radians(45))

# ============================================================
# REALISTIC BLUE SKY BACKGROUND
# ============================================================
world = bpy.data.worlds.get("ThermalWorld")
if world is None:
    world = bpy.data.worlds.new("ThermalWorld")

bpy.context.scene.world = world
world.use_nodes = True
nodes = world.node_tree.nodes
links = world.node_tree.links

for n in nodes:
    nodes.remove(n)

node_out = nodes.new('ShaderNodeOutputWorld')
node_bg = nodes.new('ShaderNodeBackground')

# Slightly softer blue so it doesn't overpower the green grass
node_bg.inputs['Color'].default_value = (0.15, 0.45, 0.85, 1.0) 
node_bg.inputs['Strength'].default_value = 0.8

links.new(node_bg.outputs['Background'], node_out.inputs['Surface'])

for area in bpy.context.screen.areas:
    if area.type == 'VIEW_3D':
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.use_scene_world = True

# ============================================================
# RENDER SETTINGS
# ============================================================
scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE'
scene.render.resolution_x = 640
scene.render.resolution_y = 480
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = False

# ============================================================
# PREPARE NATURAL MATERIALS (DO NOT TOUCH NILGAI)
# ============================================================

# We DO NOT assign anything to the nilgai here, so it keeps its original textures!
assign_material(soil, natural_soil)

for obj in grass_objects:
    assign_material(obj, natural_grass)

print("\n========================================")
print("MAIN SCENE READY (NATURAL COLORS APPLIED)")
print("========================================")