import bpy
import os
import math
import colorsys
import random

# ============================================================
# NEW TEMPERATURE & DYNAMIC WINDOW LOGIC 
# ============================================================
# Typical Ahmedabad morning air temperature
TA = 27.0  

# 1. Assign physical temperatures based on your custom rules
TEMP_MAMMAL = TA + 12.0     # Nilgai = TA + 5
TEMP_SOIL = TA + 3.0       # Soil = TA + 1
TEMP_GRASS = TA + 2.0      # Grass = TA + 1
TEMP_SKY = -40.0           # Sky capped at -40

# 2. Calculate dynamic window (excluding the -40 sky to prevent squashing)
scene_temps = [TEMP_MAMMAL, TEMP_SOIL, TEMP_GRASS]
lo = min(scene_temps)
hi = max(scene_temps)

# 3. Map temperatures to 0.0 - 1.0 grey values
def temp_to_grey(t):
    if t <= TEMP_SKY: 
        return 0.0
    if hi == lo: 
        return 0.0
    return max(0.0, min(1.0, (t - lo) / (hi - lo)))

# ============================================================
# FOLDER STRUCTURE (OUTPUT: yolo_ds_ta={TA})
# ============================================================
BASE_DIR = os.path.join(bpy.path.abspath("//"), f"yolo_ds_ta={TA}")
DIR_WHITE_HOT = os.path.join(BASE_DIR, "white_hot")
DIR_IRONBOW_RGB = os.path.join(BASE_DIR, "ironbow_rgb")
DIR_IRONBOW_HSV = os.path.join(BASE_DIR, "ironbow_hsv")
DIR_LABELS = os.path.join(BASE_DIR, "labels")

for folder in [BASE_DIR, DIR_WHITE_HOT, DIR_IRONBOW_RGB, DIR_IRONBOW_HSV, DIR_LABELS]:
    os.makedirs(folder, exist_ok=True)

bpy.context.scene.view_settings.view_transform = 'Standard'

# ============================================================
# FIND OBJECTS
# ============================================================
soil = bpy.data.objects.get("SOIL_GROUND")
nilgai = bpy.data.objects.get("mesh_0")

grass_objects = []
for obj in bpy.context.scene.objects:
    if obj.type == 'MESH' and obj.name.startswith("Object_2"):
        grass_objects.append(obj)

if soil is None or nilgai is None:
    raise RuntimeError("Run 01_GUI_Main_Scene.py first to setup objects.")

nilgai.rotation_mode = 'XYZ'

# ============================================================
# DYNAMIC LOOKUP TABLE VALUES (Mapped via Percentile Window)
# ============================================================
c_mam = temp_to_grey(TEMP_MAMMAL)
c_grs = temp_to_grey(TEMP_GRASS)
c_sol = temp_to_grey(TEMP_SOIL)

VAL_WHITE_HOT = {
    "mammal": (c_mam, c_mam, c_mam, 1.0),
    "grass":  (c_grs, c_grs, c_grs, 1.0),
    "soil":   (c_sol, c_sol, c_sol, 1.0),
    "sky":    (0.0, 0.0, 0.0, 1.0)
}

VAL_IRONBOW_RGB = {
    "mammal": (0.945, 0.400, 0.012, 1.0),
    "grass":  (0.906, 0.278, 0.082, 1.0),
    "soil":   (0.906, 0.278, 0.082, 1.0),
    "sky":    (0.000, 0.000, 0.039, 1.0)
}

VAL_MASK = {
    "mammal": (1.0, 1.0, 1.0, 1.0),
    "bg":     (0.0, 0.0, 0.0, 1.0) 
}

# ============================================================
# MATERIAL CREATOR
# ============================================================
def create_flat_material(name, color):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    
    node_emission = nodes.new(type='ShaderNodeEmission')
    node_emission.inputs['Color'].default_value = color
    node_emission.inputs['Strength'].default_value = 1.0
    
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    links.new(node_emission.outputs['Emission'], node_output.inputs['Surface'])
    return mat

def assign_material(obj, material):
    if obj is None or material is None: return
    if len(obj.data.materials) == 0:
        obj.data.materials.append(material)
    else:
        obj.data.materials[0] = material

def set_scene_materials(dataset_type):
    if dataset_type == "MASK":
        mat_animal = create_flat_material("MASK_ANIMAL", VAL_MASK["mammal"])
        mat_bg = create_flat_material("MASK_BG", VAL_MASK["bg"])
        sky_color = VAL_MASK["bg"]
        
        assign_material(nilgai, mat_animal)
        assign_material(soil, mat_bg)
        for obj in grass_objects:
            assign_material(obj, mat_bg)

    elif dataset_type == "WHITE_HOT":
        mat_animal = create_flat_material("WH_ANIMAL", VAL_WHITE_HOT["mammal"])
        mat_grass = create_flat_material("WH_GRASS", VAL_WHITE_HOT["grass"])
        mat_soil = create_flat_material("WH_SOIL", VAL_WHITE_HOT["soil"])
        sky_color = VAL_WHITE_HOT["sky"]
        
        assign_material(nilgai, mat_animal)
        assign_material(soil, mat_soil)
        for obj in grass_objects:
            assign_material(obj, mat_grass)

    elif dataset_type == "IRONBOW":
        mat_animal = create_flat_material("IB_ANIMAL", VAL_IRONBOW_RGB["mammal"])
        mat_grass = create_flat_material("IB_GRASS", VAL_IRONBOW_RGB["grass"])
        mat_soil = create_flat_material("IB_SOIL", VAL_IRONBOW_RGB["soil"])
        sky_color = VAL_IRONBOW_RGB["sky"]
        
        assign_material(nilgai, mat_animal)
        assign_material(soil, mat_soil)
        for obj in grass_objects:
            assign_material(obj, mat_grass)

    world = bpy.context.scene.world
    if world and world.use_nodes:
        bg_node = world.node_tree.nodes.get('Background')
        if bg_node:
            bg_node.inputs['Color'].default_value = sky_color

# ============================================================
# ACCURATE 2D SILHOUETTE BBOX EXTRACTION
# ============================================================
def extract_mask_bbox(pixels, w, h):
    min_x, max_x = w, -1
    min_y, max_y = h, -1
    found = False

    for i in range(0, len(pixels), 4):
        if pixels[i] > 0.5:
            found = True
            pixel_index = i // 4
            x = pixel_index % w
            y = pixel_index // w
            
            if x < min_x: min_x = x
            if x > max_x: max_x = x
            if y < min_y: min_y = y
            if y > max_y: max_y = y

    if not found:
        return None

    yolo_w = (max_x - min_x) / w
    yolo_h = (max_y - min_y) / h
    yolo_x = (min_x + max_x) / 2.0 / w
    yolo_y = (h - (min_y + max_y) / 2.0) / h

    return (yolo_x, yolo_y, yolo_w, yolo_h)

# ============================================================
# RENDER LOGIC
# ============================================================
original_location = nilgai.location.copy()
original_rotation = nilgai.rotation_euler.copy()

def render_frame(pose_name, offset_x, offset_y, rot_z):
    scene = bpy.context.scene
    
    nilgai.location.x = original_location.x + offset_x
    nilgai.location.y = original_location.y + offset_y
    nilgai.rotation_euler[2] = rot_z 
    
    bpy.context.view_layer.update()
    
    # 1. RENDER SILHOUETTE MASK & EXTRACT BBOX
    set_scene_materials("MASK")
    mask_filepath = os.path.join(BASE_DIR, "temp_mask.png")
    scene.render.filepath = mask_filepath
    bpy.ops.render.render(write_still=True)
    
    mask_img = bpy.data.images.load(mask_filepath)
    w, h = mask_img.size[0], mask_img.size[1]
    mask_pixels = list(mask_img.pixels)
    
    bbox = extract_mask_bbox(mask_pixels, w, h)
    
    bpy.data.images.remove(mask_img)
    if os.path.exists(mask_filepath):
        os.remove(mask_filepath)
        
    if bbox:
        with open(os.path.join(DIR_LABELS, f"{pose_name}.txt"), "w") as f:
            f.write(f"0 {bbox[0]:.6f} {bbox[1]:.6f} {bbox[2]:.6f} {bbox[3]:.6f}\n")
    else:
        print(f"[{pose_name}] Nilgai is 100% hidden. No bounding box generated.")

    # 2. RENDER WHITE HOT
    set_scene_materials("WHITE_HOT")
    wh_filename = f"white_hot_{pose_name}.png"
    scene.render.filepath = os.path.join(DIR_WHITE_HOT, wh_filename)
    bpy.ops.render.render(write_still=True)
    
    # 3. RENDER IRONBOW RGB & SAVE HSV IMAGE
    set_scene_materials("IRONBOW")
    ib_filename = f"ironbow_rgb_{pose_name}.png"
    ib_filepath = os.path.join(DIR_IRONBOW_RGB, ib_filename)
    scene.render.filepath = ib_filepath
    bpy.ops.render.render(write_still=True)
    
    ib_img = bpy.data.images.load(ib_filepath)
    ib_pixels = list(ib_img.pixels)
    hsv_image_pixels = []
    
    for i in range(0, len(ib_pixels), 4):
        r, g, b = ib_pixels[i], ib_pixels[i+1], ib_pixels[i+2]
        h_fl, s_fl, v_fl = colorsys.rgb_to_hsv(r, g, b)
        hsv_image_pixels.extend([h_fl, s_fl, v_fl, 1.0])

    hsv_img_name = f"ironbow_hsv_{pose_name}"
    hsv_img = bpy.data.images.get(hsv_img_name)
    if hsv_img:
        bpy.data.images.remove(hsv_img)
        
    hsv_img = bpy.data.images.new(hsv_img_name, width=w, height=h)
    hsv_img.pixels = hsv_image_pixels
    hsv_img.filepath_raw = os.path.join(DIR_IRONBOW_HSV, f"ironbow_hsv_{pose_name}.png")
    hsv_img.file_format = 'PNG'
    hsv_img.save()
    
    bpy.data.images.remove(ib_img)
    bpy.data.images.remove(hsv_img)

    print(f"Generated frame: {pose_name}")

# ============================================================
# RUN 100 RANDOMIZED FRAMES
# ============================================================
print("\n========================================")
print(f"STARTING 100-FRAME MASKED DATASET GENERATION (Ta={TA}°C)")
print("========================================")

TOTAL_FRAMES = 100

for frame in range(TOTAL_FRAMES):
    pose_name = f"frame_{frame:04d}"
    
    rand_x = random.uniform(-1.5, 1.5)
    rand_y = random.uniform(-1.5, 1.5)
    rand_rot_z = random.uniform(0, math.pi * 2)
    
    render_frame(pose_name, rand_x, rand_y, rand_rot_z)

# Restore Original Position and Rotation
nilgai.location = original_location
nilgai.rotation_euler = original_rotation

print("\n========================================")
print(f"SUCCESS: 100 FRAMES SAVED TO yolo_ds_ta={TA}")
print("========================================")