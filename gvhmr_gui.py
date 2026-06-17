"""
MocapOS — Modern GUI for GVHMR Motion Capture
Full Body + Hands Motion Capture with CustomTkinter
"""

import sys
import os
import re
import ctypes
import shutil
import zipfile
import webbrowser
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path

import customtkinter as ctk

# Project root
PROJ_ROOT = Path(__file__).resolve().parent
ENV_NAME = "gvhmr"


def _candidate_env_dirs():
    """Conda env directories to search, in priority order.

    The portable deliverable ships a self-contained env at PROJ_ROOT/env, which
    must win so the app never depends on the user having miniconda3 in a fixed
    place. Falls back to the env that this GUI is currently running inside, then
    to the usual miniconda3/anaconda3 locations."""
    cands = [
        PROJ_ROOT / "env",                       # portable bundle (preferred)
        Path(sys.executable).parent,             # env this GUI runs inside
    ]
    for base in (
        Path.home() / "miniconda3", Path.home() / "anaconda3",
        Path.home() / "miniforge3", Path.home() / "Mambaforge",
        Path("C:/miniconda3"), Path("C:/anaconda3"),
        Path("C:/ProgramData/miniconda3"), Path("C:/ProgramData/anaconda3"),
    ):
        cands.append(base / "envs" / ENV_NAME)
    return cands


def _resolve_env_dir():
    """Return the conda env directory that actually contains a python.exe."""
    for d in _candidate_env_dirs():
        if (d / "python.exe").exists():
            return d
    return PROJ_ROOT / "env"  # best-effort default for clear error messages


ENV_DIR = _resolve_env_dir()
CONDA_BAT = str(ENV_DIR.parent.parent / "condabin" / "conda.bat")


def _env_python(windowed=False):
    """Path to python.exe (or pythonw.exe) of the resolved env."""
    return str(ENV_DIR / ("pythonw.exe" if windowed else "python.exe"))


def _env_tool(name: str):
    """Locate a binary (e.g. ffmpeg/ffprobe) in the env's Library\\bin or Scripts,
    then on PATH. Returns None if not found."""
    for sub in ("Library/bin", "Scripts", ""):
        cand = ENV_DIR / sub / f"{name}.exe" if sub else ENV_DIR / f"{name}.exe"
        if cand.exists():
            return str(cand)
    return shutil.which(name)

# ═══════════════════════════════════════════════════════
# TRADUCCIONES
# ═══════════════════════════════════════════════════════
TRANSLATIONS = {
    "en": {
        "lang_name": "English",
        "inference": "Inference",
        "inference_sub": "Process video to extract full-body motion capture data",
        "skeleton_transfer": "Skeleton Transfer",
        "skeleton_sub": "Transfer motion to your Mixamo character",
        "export_bvh": "Export BVH",
        "export_sub": "Export motion capture data to BVH format for 3D software",
        "settings": "Settings",
        "settings_sub": "Environment status and system information",
        "video_input": "Video Input",
        "video_file": "Video file:",
        "output_dir": "Output Directory",
        "output": "Output:",
        "options": "Options",
        "static_cam": "Static Camera (-s)",
        "static_cam_tip": "If your camera is on a tripod or not moving, enable this.\nIt skips camera-motion estimation and makes processing faster.",
        "use_dpvo": "Use DPVO",
        "use_dpvo_tip": "Estimates how the camera moves through the scene.\nDPVO = more accurate but slower. SimpleVO = faster default.\nOnly change this if the result looks shaky or wrong.",
        "verbose": "Verbose (save intermediates)",
        "verbose_tip": "Saves extra debug files (images, masks, 3D previews)\ninside the output folder. Useful only if something\nlooks wrong and you need to inspect the steps.",
        "hands": "Full Body + Hands (HaMeR)",
        "hands_tip": "Tracks fingers and hand poses in addition to the body.\nSlower but needed if you want realistic hand animation.\nDisable if you only need body motion.",
        "focal": "Custom Focal Length (mm):",
        "focal_tip": "The focal length is how zoomed-in your camera is.\nIf you know your lens (e.g. 24mm, 50mm), enter it here\nfor more accurate 3D depth results.",
        "focal_entry_tip": "Typical values: 24mm (wide/GoPro), 50mm (standard),\n85mm (telephoto/phone zoom). If unsure, leave default.",
        "run_inference": "▶  Run Inference",
        "stop": "⏹  Stop",
        "open_output": "📁 Open Output",
        "export_info": "Export motion capture data to BVH format for retargeting to your 3D characters.",
        "export_compat": "Compatible with: Blender, Unity, Unreal Engine, Maya, 3ds Max, Mixamo",
        "results_dir": "Results Directory",
        "dir": "Dir:",
        "results_tip": "Select the output folder created after running Inference.\nIt contains the motion data file (hmr4d_results.pt).",
        "output_file": "Output File",
        "file": "File:",
        "output_tip": "Where to save the .bvh animation file.\nIf left empty, it will be named automatically.",
        "export_opts": "Export Options",
        "body_only": "Body Only (22 joints) — skip hands/face",
        "body_only_tip": "Exports only the main body skeleton (22 bones).\nUse this if your 3D character does not have\ndetailed fingers or face rigging.",
        "fps": "FPS:",
        "fps_tip": "How many frames per second the animation should have.\n30 fps is standard for most projects. Match your video\nframe rate if you want perfect sync.",
        "scale": "Scale:",
        "scale_tip": "Size scale of the exported skeleton.\n100 = centimeters (default for most 3D apps).\n1 = meters. Use 100 unless your software expects meters.",
        "export_bvh_btn": "📤 Export BVH",
        "howto_title": "How to Retarget to Your Character",
        "anim_source": "Animation Source",
        "results_folder": "Results folder:",
        "results_folder_tip": "Select the folder created after running Inference.\nIt must contain the hmr4d_results.pt file.",
        "char": "Character (FBX / DAE)",
        "char_file": "File:",
        "char_tip": "Your 3D character file (FBX or DAE) with a Mixamo skeleton.\nAny rest pose works — T-Pose, A-Pose or a natural/relaxed bind.\nThe motion is matched in absolute pose.",
        "char_format": "(.fbx / .dae  —  Mixamo skeleton, any pose)",
        "char_warn": "✓  Works with any rest pose (T-Pose, A-Pose, natural). Mixamo skeleton required.",
        "blender": "Blender",
        "blender_exe": "Executable:",
        "blender_tip": "Blender is used behind the scenes to transfer the motion\nto your character. Click Auto-detect to find it, or browse\nto your Blender installation folder.",
        "export_options": "Export Options",
        "format": "Format:",
        "format_tip": "File format for the final animated character.\nFBX = works everywhere (Blender, Unity, Unreal, Maya).\nGLB = for web viewers. GLTF = open standard.",
        "retarget_fps_tip": "Frames per second of the final animation.\n30 fps is standard. Match your source video for best results.",
        "out_path": "Output:",
        "out_path_tip": "Where to save the final animated character.\nThe file extension changes automatically based on\nthe format you selected above.",
        "transfer_btn": "🦴 Transfer & Export",
        "how_works": "How it works",
        "workflow_1": "Workflow:",
        "workflow_2": "  1. Run Inference on your video  →  folder with hmr4d_results.pt",
        "workflow_3": "  2. Select that folder and the Mixamo FBX (e.g. X Bot.fbx)",
        "workflow_4": "  3. Press 'Transfer & Export'  →  animated character with Mixamo bones",
        "workflow_5": "Formats:  FBX · GLB · GLTF · ABC · DAE   |   Requires: Blender 3.x / 4.x / 5.x",
        "env": "Environment",
        "proj_root": "Project Root:",
        "conda_env": "Conda Env:",
        "python": "Python:",
        "checkpoints": "Model Checkpoints",
        "body_models": "Body Models Importer (SMPL / SMPL-X)",
        "body_models_intro": "SMPL and SMPL-X are required for rendering but cannot be redistributed — you must register on the Max Planck site and download them yourself. This importer extracts the right files from the downloaded zip and places them in the correct folder (renaming SMPL files for you).",
        "smplx_step1": "1.  Open https://smpl-x.is.tue.mpg.de/  →  register and login",
        "smplx_step2": "2.  Go to Download → click the button labelled exactly:",
        "smplx_step2b": "      'Download SMPL-X v1.1 (NPZ+PKL, 830 MB) - Use this for SMPL-X Python codebase'",
        "smplx_step3": "3.  Pick the downloaded zip below (models_smplx_v1_1.zip).",
        "smpl_step1": "1.  Open https://smpl.is.tue.mpg.de/  →  register and login",
        "smpl_step2": "2.  Go to Download → click:",
        "smpl_step2b": "      'Version 1.1.0 for Python 2.7 (female/male/neutral, 247 MB)'",
        "smpl_step3": "3.  Pick the downloaded zip below (SMPL_python_v.1.1.0.zip).",
        "open_smplx_site": "🌐 Open SMPL-X site",
        "open_smpl_site": "🌐 Open SMPL site",
        "import_smplx_zip": "📦 Import SMPL-X zip",
        "import_smpl_zip": "📦 Import SMPL zip",
        "mano_step1": "1.  Open https://mano.is.tue.mpg.de/  →  register and login",
        "mano_step2": "2.  Go to Download → click the first link:",
        "mano_step2b": "      'Models & Code (mano_v1_2.zip)'",
        "mano_step3": "3.  Pick the downloaded zip below (mano_v1_2.zip).",
        "open_mano_site": "🌐 Open MANO site",
        "import_mano_zip": "📦 Import MANO zip",
        "setup_title": "Setup needed",
        "setup_msg": "Some models are not installed yet:\n\n  Required (body render): {req}\n  Hands (optional): {mano}\n\nUse the importers on this Settings page to install them. Once installed, this notice won't appear again.",
        "check_gpu": "🎮 Check GPU Info",
        "open_proj": "📂 Open Project Folder",
        "uninstall": "🗑 Uninstall / Free space",
        "console": "Console Output",
        "show_console": "Show Console ▼",
        "hide_console": "Hide Console ▲",
        "ready": "Ready",
        "running": "Running: {0}...",
        "completed": "Completed!",
        "failed": "Failed (code {0})",
        "stopped": "Stopped by user",
        "browse": "Browse",
        "auto_detect": "Auto-detect",
        "folder_hint": "Folder with hmr4d_results.pt — outputs Mixamo skeleton directly",
        "leave_empty": "(leave empty for auto)",
    },
    "es": {
        "lang_name": "Español",
        "inference": "Inferencia",
        "inference_sub": "Procesa video para extraer datos de captura de movimiento de cuerpo completo",
        "skeleton_transfer": "Transferencia de Esqueleto",
        "skeleton_sub": "Transfiere el movimiento a tu personaje Mixamo",
        "export_bvh": "Exportar BVH",
        "export_sub": "Exporta datos de captura a formato BVH para software 3D",
        "settings": "Configuración",
        "settings_sub": "Estado del entorno e información del sistema",
        "video_input": "Entrada de Video",
        "video_file": "Archivo de video:",
        "output_dir": "Directorio de Salida",
        "output": "Salida:",
        "options": "Opciones",
        "static_cam": "Cámara Estática (-s)",
        "static_cam_tip": "Si tu cámara está en un trípode o no se mueve, activa esto.\nOmite el cálculo de movimiento de cámara y hace el proceso más rápido.",
        "use_dpvo": "Usar DPVO",
        "use_dpvo_tip": "Calcula cómo se mueve la cámara por la escena.\nDPVO = más preciso pero más lento. SimpleVO = más rápido (por defecto).\nCámbialo solo si el resultado se ve inestable o incorrecto.",
        "verbose": "Verbose (guardar intermedios)",
        "verbose_tip": "Guarda archivos extra de depuración (imágenes, máscaras, vistas 3D)\nen la carpeta de salida. Útil solo si algo se ve mal\ny necesitas revisar los pasos intermedios.",
        "hands": "Cuerpo + Manos (HaMeR)",
        "hands_tip": "Rastrea dedos y manos además del cuerpo.\nMás lento pero necesario si quieres animación realista de manos.\nDesactívalo si solo necesitas movimiento corporal.",
        "focal": "Distancia Focal personalizada (mm):",
        "focal_tip": "La distancia focal es qué tan zoom tiene tu cámara.\nSi conoces tu lente (ej. 24mm, 50mm), ingrésalo aquí\npara resultados de profundidad 3D más precisos.",
        "focal_entry_tip": "Valores típicos: 24mm (gran angular/GoPro), 50mm (estándar),\n85mm (telefoto/zoom de celular). Si no estás seguro, deja el valor por defecto.",
        "run_inference": "▶  Ejecutar Inferencia",
        "stop": "⏹  Detener",
        "open_output": "📁 Abrir Salida",
        "export_info": "Exporta datos de captura a formato BVH para retargeting a tus personajes 3D.",
        "export_compat": "Compatible con: Blender, Unity, Unreal Engine, Maya, 3ds Max, Mixamo",
        "results_dir": "Directorio de Resultados",
        "dir": "Carpeta:",
        "results_tip": "Selecciona la carpeta de salida creada después de ejecutar Inferencia.\nContiene el archivo de datos de movimiento (hmr4d_results.pt).",
        "output_file": "Archivo de Salida",
        "file": "Archivo:",
        "output_tip": "Dónde guardar el archivo de animación .bvh.\nSi lo dejas vacío, se nombrará automáticamente.",
        "export_opts": "Opciones de Exportación",
        "body_only": "Solo Cuerpo (22 joints) — omitir manos/cara",
        "body_only_tip": "Exporta solo el esqueleto corporal principal (22 huesos).\nÚsalo si tu personaje 3D no tiene dedos detallados\nni rigging facial.",
        "fps": "FPS:",
        "fps_tip": "Cuántos fotogramas por segundo tendrá la animación.\n30 fps es el estándar para la mayoría de proyectos.\nIguala el fps de tu video para sincronización perfecta.",
        "scale": "Escala:",
        "scale_tip": "Escala de tamaño del esqueleto exportado.\n100 = centímetros (estándar para la mayoría de apps 3D).\n1 = metros. Usa 100 a menos que tu software use metros.",
        "export_bvh_btn": "📤 Exportar BVH",
        "howto_title": "Cómo hacer Retarget a tu Personaje",
        "anim_source": "Origen de Animación",
        "results_folder": "Carpeta de resultados:",
        "results_folder_tip": "Selecciona la carpeta creada después de ejecutar Inferencia.\nDebe contener el archivo hmr4d_results.pt.",
        "char": "Personaje (FBX / DAE)",
        "char_file": "Archivo:",
        "char_tip": "Tu archivo de personaje 3D (FBX o DAE) con esqueleto Mixamo.\nCualquier pose de reposo funciona — T-Pose, A-Pose o un bind natural/relajado.\nEl movimiento se ajusta en pose absoluta.",
        "char_format": "(.fbx / .dae  —  esqueleto Mixamo, cualquier pose)",
        "char_warn": "✓  Funciona con cualquier pose (T-Pose, A-Pose, natural). Requiere esqueleto Mixamo.",
        "blender": "Blender",
        "blender_exe": "Ejecutable:",
        "blender_tip": "Blender se usa en segundo plano para transferir el movimiento\na tu personaje. Presiona Auto-detectar para encontrarlo, o navega\nmanualmente a tu carpeta de instalación de Blender.",
        "export_options": "Opciones de Exportación",
        "format": "Formato:",
        "format_tip": "Formato del personaje animado final.\nFBX = funciona en todas partes (Blender, Unity, Unreal, Maya).\nGLB = para visualizadores web. GLTF = estándar abierto.",
        "retarget_fps_tip": "Fotogramas por segundo de la animación final.\n30 fps es estándar. Iguala tu video de origen para mejores resultados.",
        "out_path": "Salida:",
        "out_path_tip": "Dónde guardar el personaje animado final.\nLa extensión del archivo cambia automáticamente según\nel formato seleccionado arriba.",
        "transfer_btn": "🦴 Transferir y Exportar",
        "how_works": "Cómo funciona",
        "workflow_1": "Flujo de trabajo:",
        "workflow_2": "  1. Ejecuta Inferencia en tu video  →  carpeta con hmr4d_results.pt",
        "workflow_3": "  2. Selecciona esa carpeta y el FBX Mixamo (ej. X Bot.fbx)",
        "workflow_4": "  3. Presiona 'Transferir y Exportar'  →  personaje animado con huesos Mixamo",
        "workflow_5": "Formatos:  FBX · GLB · GLTF · ABC · DAE   |   Requiere: Blender 3.x / 4.x / 5.x",
        "env": "Entorno",
        "proj_root": "Raíz del Proyecto:",
        "conda_env": "Entorno Conda:",
        "python": "Python:",
        "checkpoints": "Checkpoints de Modelos",
        "body_models": "Importador de Body Models (SMPL / SMPL-X)",
        "body_models_intro": "SMPL y SMPL-X son obligatorios para renderizar pero no se pueden redistribuir — tienes que registrarte en el sitio de Max Planck y descargarlos tú mismo. Este importador extrae los archivos correctos del zip descargado y los pone en la carpeta correcta (renombrando los SMPL automáticamente).",
        "smplx_step1": "1.  Abre https://smpl-x.is.tue.mpg.de/  →  regístrate e inicia sesión",
        "smplx_step2": "2.  Ve a Download → haz clic en el botón que dice exactamente:",
        "smplx_step2b": "      'Download SMPL-X v1.1 (NPZ+PKL, 830 MB) - Use this for SMPL-X Python codebase'",
        "smplx_step3": "3.  Selecciona el zip descargado abajo (models_smplx_v1_1.zip).",
        "smpl_step1": "1.  Abre https://smpl.is.tue.mpg.de/  →  regístrate e inicia sesión",
        "smpl_step2": "2.  Ve a Download → haz clic en:",
        "smpl_step2b": "      'Version 1.1.0 for Python 2.7 (female/male/neutral, 247 MB)'",
        "smpl_step3": "3.  Selecciona el zip descargado abajo (SMPL_python_v.1.1.0.zip).",
        "open_smplx_site": "🌐 Abrir sitio SMPL-X",
        "open_smpl_site": "🌐 Abrir sitio SMPL",
        "import_smplx_zip": "📦 Importar zip SMPL-X",
        "import_smpl_zip": "📦 Importar zip SMPL",
        "mano_step1": "1.  Abre https://mano.is.tue.mpg.de/  →  regístrate e inicia sesión",
        "mano_step2": "2.  Ve a Download → haz clic en el primer enlace:",
        "mano_step2b": "      'Models & Code (mano_v1_2.zip)'",
        "mano_step3": "3.  Selecciona el zip descargado abajo (mano_v1_2.zip).",
        "open_mano_site": "🌐 Abrir sitio MANO",
        "import_mano_zip": "📦 Importar zip MANO",
        "setup_title": "Falta instalar modelos",
        "setup_msg": "Aún faltan modelos por instalar:\n\n  Obligatorios (render del cuerpo): {req}\n  Manos (opcional): {mano}\n\nUsa los importadores de esta página de Ajustes para instalarlos. Una vez instalados, este aviso no volverá a aparecer.",
        "check_gpu": "🎮 Verificar GPU",
        "open_proj": "📂 Abrir Carpeta del Proyecto",
        "uninstall": "🗑 Desinstalar / Liberar espacio",
        "console": "Salida de Consola",
        "show_console": "Mostrar Consola ▼",
        "hide_console": "Ocultar Consola ▲",
        "ready": "Listo",
        "running": "Ejecutando: {0}...",
        "completed": "¡Completado!",
        "failed": "Falló (código {0})",
        "stopped": "Detenido por el usuario",
        "browse": "Explorar",
        "auto_detect": "Auto-detectar",
        "folder_hint": "Carpeta con hmr4d_results.pt — exporta esqueleto Mixamo directamente",
        "leave_empty": "(déjalo vacío para automático)",
    },
    "fr": {
        "lang_name": "Français",
        "inference": "Inférence",
        "inference_sub": "Traiter la vidéo pour extraire les données de capture de mouvement du corps",
        "skeleton_transfer": "Transfert de Squelette",
        "skeleton_sub": "Transférer le mouvement à votre personnage Mixamo",
        "export_bvh": "Exporter BVH",
        "export_sub": "Exporter les données de capture au format BVH pour logiciels 3D",
        "settings": "Paramètres",
        "settings_sub": "État de l'environnement et informations système",
        "video_input": "Entrée Vidéo",
        "video_file": "Fichier vidéo:",
        "output_dir": "Répertoire de Sortie",
        "output": "Sortie:",
        "options": "Options",
        "static_cam": "Caméra Statique (-s)",
        "static_cam_tip": "Si votre caméra est sur un trépied ou ne bouge pas, activez ceci.\nIl ignore l'estimation du mouvement de caméra et accélère le traitement.",
        "use_dpvo": "Utiliser DPVO",
        "use_dpvo_tip": "Estime comment la caméra se déplace dans la scène.\nDPVO = plus précis mais plus lent. SimpleVO = plus rapide (par défaut).\nChangez ceci uniquement si le résultat semble instable ou incorrect.",
        "verbose": "Verbose (sauver intermédiaires)",
        "verbose_tip": "Sauvegarde des fichiers de débogage supplémentaires (images, masques, aperçus 3D)\ndans le dossier de sortie. Utile uniquement si quelque chose semble incorrect\net que vous devez inspecter les étapes.",
        "hands": "Corps + Mains (HaMeR)",
        "hands_tip": "Piste les doigts et les mains en plus du corps.\nPlus lent mais nécessaire si vous voulez une animation de mains réaliste.\nDésactivez si vous n'avez besoin que du mouvement corporel.",
        "focal": "Longueur Focale personnalisée (mm):",
        "focal_tip": "La distance focale correspond au zoom de votre caméra.\nSi vous connaissez votre objectif (ex. 24mm, 50mm), entrez-le ici\npour des résultats de profondeur 3D plus précis.",
        "focal_entry_tip": "Valeurs typiques : 24mm (grand-angle/GoPro), 50mm (standard),\n85mm (téléphoto/zoom téléphone). En cas de doute, laissez la valeur par défaut.",
        "run_inference": "▶  Lancer l'Inférence",
        "stop": "⏹  Arrêter",
        "open_output": "📁 Ouvrir la Sortie",
        "export_info": "Exportez les données de capture au format BVH pour le retargeting vers vos personnages 3D.",
        "export_compat": "Compatible avec: Blender, Unity, Unreal Engine, Maya, 3ds Max, Mixamo",
        "results_dir": "Répertoire des Résultats",
        "dir": "Dossier:",
        "results_tip": "Sélectionnez le dossier de sortie créé après avoir exécuté l'Inférence.\nIl contient le fichier de données de mouvement (hmr4d_results.pt).",
        "output_file": "Fichier de Sortie",
        "file": "Fichier:",
        "output_tip": "Où sauvegarder le fichier d'animation .bvh.\nSi laissé vide, il sera nommé automatiquement.",
        "export_opts": "Options d'Exportation",
        "body_only": "Corps Seul (22 joints) — ignorer mains/visage",
        "body_only_tip": "Exporte uniquement le squelette corporel principal (22 os).\nUtilisez ceci si votre personnage 3D n'a pas de doigts détaillés\nni de rigging facial.",
        "fps": "FPS:",
        "fps_tip": "Nombre d'images par seconde de l'animation.\n30 fps est la norme pour la plupart des projets.\nFaites correspondre le fps de votre vidéo pour une synchronisation parfaite.",
        "scale": "Échelle:",
        "scale_tip": "Échelle de taille du squelette exporté.\n100 = centimètres (norme pour la plupart des apps 3D).\n1 = mètres. Utilisez 100 sauf si votre logiciel attend des mètres.",
        "export_bvh_btn": "📤 Exporter BVH",
        "howto_title": "Comment faire du Retarget vers votre Personnage",
        "anim_source": "Source d'Animation",
        "results_folder": "Dossier de résultats:",
        "results_folder_tip": "Sélectionnez le dossier créé après avoir exécuté l'Inférence.\nIl doit contenir le fichier hmr4d_results.pt.",
        "char": "Personnage (FBX / DAE)",
        "char_file": "Fichier:",
        "char_tip": "Votre fichier de personnage 3D (FBX ou DAE) avec un squelette Mixamo.\nN'importe quelle pose de repos fonctionne — T-Pose, A-Pose ou un bind naturel.\nLe mouvement est appliqué en pose absolue.",
        "char_format": "(.fbx / .dae  —  squelette Mixamo, toute pose)",
        "char_warn": "✓  Fonctionne avec toute pose de repos (T-Pose, A-Pose, naturelle). Squelette Mixamo requis.",
        "blender": "Blender",
        "blender_exe": "Exécutable:",
        "blender_tip": "Blender est utilisé en arrière-plan pour transférer le mouvement\nà votre personnage. Cliquez sur Auto-détecter pour le trouver, ou naviguez\nmanuellement vers votre dossier d'installation de Blender.",
        "export_options": "Options d'Exportation",
        "format": "Format:",
        "format_tip": "Format du personnage animé final.\nFBX = fonctionne partout (Blender, Unity, Unreal, Maya).\nGLB = pour visionneuses web. GLTF = standard ouvert.",
        "retarget_fps_tip": "Images par seconde de l'animation finale.\n30 fps est la norme. Faites correspondre votre vidéo source pour de meilleurs résultats.",
        "out_path": "Sortie:",
        "out_path_tip": "Où sauvegarder le personnage animé final.\nL'extension du fichier change automatiquement selon\nle format sélectionné ci-dessus.",
        "transfer_btn": "🦴 Transférer et Exporter",
        "how_works": "Comment ça marche",
        "workflow_1": "Flux de travail:",
        "workflow_2": "  1. Lancez l'Inférence sur votre vidéo  →  dossier avec hmr4d_results.pt",
        "workflow_3": "  2. Sélectionnez ce dossier et le FBX Mixamo (ex. X Bot.fbx)",
        "workflow_4": "  3. Appuyez sur 'Transférer et Exporter'  →  personnage animé avec squelette Mixamo",
        "workflow_5": "Formats:  FBX · GLB · GLTF · ABC · DAE   |   Nécessite: Blender 3.x / 4.x / 5.x",
        "env": "Environnement",
        "proj_root": "Racine du Projet:",
        "conda_env": "Env Conda:",
        "python": "Python:",
        "checkpoints": "Checkpoints des Modèles",
        "body_models": "Importateur de Body Models (SMPL / SMPL-X)",
        "body_models_intro": "SMPL et SMPL-X sont nécessaires pour le rendu mais ne peuvent être redistribués — vous devez vous inscrire sur le site Max Planck et les télécharger vous-même. Cet importateur extrait les bons fichiers du zip et les place au bon endroit (en renommant SMPL automatiquement).",
        "smplx_step1": "1.  Ouvrez https://smpl-x.is.tue.mpg.de/  →  inscrivez-vous et connectez-vous",
        "smplx_step2": "2.  Allez sur Download → cliquez exactement sur :",
        "smplx_step2b": "      'Download SMPL-X v1.1 (NPZ+PKL, 830 MB) - Use this for SMPL-X Python codebase'",
        "smplx_step3": "3.  Sélectionnez le zip téléchargé ci-dessous (models_smplx_v1_1.zip).",
        "smpl_step1": "1.  Ouvrez https://smpl.is.tue.mpg.de/  →  inscrivez-vous et connectez-vous",
        "smpl_step2": "2.  Allez sur Download → cliquez sur :",
        "smpl_step2b": "      'Version 1.1.0 for Python 2.7 (female/male/neutral, 247 MB)'",
        "smpl_step3": "3.  Sélectionnez le zip téléchargé ci-dessous (SMPL_python_v.1.1.0.zip).",
        "open_smplx_site": "🌐 Ouvrir le site SMPL-X",
        "open_smpl_site": "🌐 Ouvrir le site SMPL",
        "import_smplx_zip": "📦 Importer le zip SMPL-X",
        "import_smpl_zip": "📦 Importer le zip SMPL",
        "mano_step1": "1.  Ouvrez https://mano.is.tue.mpg.de/  →  inscrivez-vous et connectez-vous",
        "mano_step2": "2.  Allez sur Download → cliquez sur le premier lien :",
        "mano_step2b": "      'Models & Code (mano_v1_2.zip)'",
        "mano_step3": "3.  Sélectionnez le zip téléchargé ci-dessous (mano_v1_2.zip).",
        "open_mano_site": "🌐 Ouvrir le site MANO",
        "import_mano_zip": "📦 Importer le zip MANO",
        "setup_title": "Installation requise",
        "setup_msg": "Certains modèles ne sont pas encore installés :\n\n  Requis (rendu du corps) : {req}\n  Mains (optionnel) : {mano}\n\nUtilisez les importateurs de cette page Paramètres pour les installer. Une fois installés, cet avis ne réapparaîtra plus.",
        "check_gpu": "🎮 Vérifier le GPU",
        "open_proj": "📂 Ouvrir le Dossier du Projet",
        "uninstall": "🗑 Désinstaller / Libérer de l'espace",
        "console": "Sortie Console",
        "show_console": "Afficher Console ▼",
        "hide_console": "Masquer Console ▲",
        "ready": "Prêt",
        "running": "Exécution: {0}...",
        "completed": "Terminé!",
        "failed": "Échoué (code {0})",
        "stopped": "Arrêté par l'utilisateur",
        "browse": "Parcourir",
        "auto_detect": "Auto-détecter",
        "folder_hint": "Dossier avec hmr4d_results.pt — exporte directement le squelette Mixamo",
        "leave_empty": "(laissez vide pour auto)",
    },
    "pt": {
        "lang_name": "Português",
        "inference": "Inferência",
        "inference_sub": "Processa vídeo para extrair dados de captura de movimento de corpo inteiro",
        "skeleton_transfer": "Transferência de Esqueleto",
        "skeleton_sub": "Transferir o movimento para seu personagem Mixamo",
        "export_bvh": "Exportar BVH",
        "export_sub": "Exporta dados de captura para formato BVH para softwares 3D",
        "settings": "Configurações",
        "settings_sub": "Estado do ambiente e informações do sistema",
        "video_input": "Entrada de Vídeo",
        "video_file": "Arquivo de vídeo:",
        "output_dir": "Diretório de Saída",
        "output": "Saída:",
        "options": "Opções",
        "static_cam": "Câmera Estática (-s)",
        "static_cam_tip": "Se sua câmera está em um tripé ou não se move, ative isto.\nPula o cálculo de movimento da câmera e torna o processo mais rápido.",
        "use_dpvo": "Usar DPVO",
        "use_dpvo_tip": "Calcula cómo se mueve la cámara por la escena.\nDPVO = más preciso pero más lento. SimpleVO = más rápido (por defecto).\nCámbialo solo si el resultado se ve inestable o incorrecto.",
        "verbose": "Verbose (salvar intermediários)",
        "verbose_tip": "Salva arquivos extras de depuração (imagens, máscaras, previews 3D)\nna pasta de saída. Útil apenas se algo parecer errado\ne você precisar revisar os passos intermediários.",
        "hands": "Corpo + Mãos (HaMeR)",
        "hands_tip": "Rastreia dedos e mãos além do corpo.\nMais lento mas necessário se quiser animação realista de mãos.\nDesative se só precisar de movimento corporal.",
        "focal": "Distância Focal personalizada (mm):",
        "focal_tip": "A distância focal é o zoom da sua câmera.\nSe conhece sua lente (ex. 24mm, 50mm), digite aqui\npara resultados de profundidade 3D mais precisos.",
        "focal_entry_tip": "Valores típicos: 24mm (grande angular/GoPro), 50mm (padrão),\n85mm (telefoto/zoom de celular). Se não tiver certeza, deixe o valor padrão.",
        "run_inference": "▶  Executar Inferência",
        "stop": "⏹  Parar",
        "open_output": "📁 Abrir Saída",
        "export_info": "Exporta dados de captura para formato BVH para retargeting aos seus personagens 3D.",
        "export_compat": "Compatível com: Blender, Unity, Unreal Engine, Maya, 3ds Max, Mixamo",
        "results_dir": "Diretório de Resultados",
        "dir": "Pasta:",
        "results_tip": "Selecione a pasta de saída criada após executar a Inferência.\nContém o arquivo de dados de movimento (hmr4d_results.pt).",
        "output_file": "Arquivo de Saída",
        "file": "Arquivo:",
        "output_tip": "Onde salvar o arquivo de animação .bvh.\nSe deixado vazio, será nomeado automaticamente.",
        "export_opts": "Opções de Exportação",
        "body_only": "Apenas Corpo (22 joints) — ignorar mãos/rosto",
        "body_only_tip": "Exporta apenas o esqueleto corporal principal (22 ossos).\nUse isto se seu personagem 3D não tem dedos detalhados\nou rigging facial.",
        "fps": "FPS:",
        "fps_tip": "Quantos quadros por segundo a animação terá.\n30 fps é o padrão para a maioria dos projetos.\nIgual ao fps do seu vídeo para sincronização perfeita.",
        "scale": "Escala:",
        "scale_tip": "Escala de tamanho do esqueleto exportado.\n100 = centímetros (padrão para a maioria dos apps 3D).\n1 = metros. Use 100 a menos que seu software use metros.",
        "export_bvh_btn": "📤 Exportar BVH",
        "howto_title": "Como fazer Retarget para seu Personagem",
        "anim_source": "Fonte de Animação",
        "results_folder": "Pasta de resultados:",
        "results_folder_tip": "Selecione a pasta criada após executar a Inferência.\nDeve conter o arquivo hmr4d_results.pt.",
        "char": "Personagem (FBX / DAE)",
        "char_file": "Arquivo:",
        "char_tip": "Seu arquivo de personagem 3D (FBX ou DAE) com esqueleto Mixamo.\nQualquer pose de descanso funciona — T-Pose, A-Pose ou um bind natural.\nO movimento é aplicado em pose absoluta.",
        "char_format": "(.fbx / .dae  —  esqueleto Mixamo, qualquer pose)",
        "char_warn": "✓  Funciona com qualquer pose (T-Pose, A-Pose, natural). Requer esqueleto Mixamo.",
        "blender": "Blender",
        "blender_exe": "Executável:",
        "blender_tip": "Blender é usado em segundo plano para transferir o movimento\npara seu personagem. Pressione Auto-detectar para encontrá-lo, ou navegue\nmanualmente até sua pasta de instalação do Blender.",
        "export_options": "Opções de Exportação",
        "format": "Formato:",
        "format_tip": "Formato do personagem animado final.\nFBX = funciona em qualquer lugar (Blender, Unity, Unreal, Maya).\nGLB = para visualizadores web. GLTF = padrão aberto.",
        "retarget_fps_tip": "Quadros por segundo da animação final.\n30 fps é o padrão. Igual ao seu vídeo de origem para melhores resultados.",
        "out_path": "Saída:",
        "out_path_tip": "Onde salvar o personagem animado final.\nA extensão do arquivo muda automaticamente de acordo\ncom o formato selecionado acima.",
        "transfer_btn": "🦴 Transferir e Exportar",
        "how_works": "Como funciona",
        "workflow_1": "Fluxo de trabalho:",
        "workflow_2": "  1. Execute Inferência no seu vídeo  →  pasta com hmr4d_results.pt",
        "workflow_3": "  2. Selecione essa pasta e o FBX Mixamo (ex. X Bot.fbx)",
        "workflow_4": "  3. Pressione 'Transferir e Exportar'  →  personagem animado com ossos Mixamo",
        "workflow_5": "Formatos:  FBX · GLB · GLTF · ABC · DAE   |   Requer: Blender 3.x / 4.x / 5.x",
        "env": "Ambiente",
        "proj_root": "Raiz do Projeto:",
        "conda_env": "Env Conda:",
        "python": "Python:",
        "checkpoints": "Checkpoints de Modelos",
        "body_models": "Importador de Body Models (SMPL / SMPL-X)",
        "body_models_intro": "SMPL e SMPL-X são necessários para renderização mas não podem ser redistribuídos — você precisa se registrar no site da Max Planck e baixá-los. Este importador extrai os arquivos certos do zip baixado e os coloca na pasta correta (renomeando os SMPL automaticamente).",
        "smplx_step1": "1.  Abra https://smpl-x.is.tue.mpg.de/  →  registre-se e faça login",
        "smplx_step2": "2.  Vá em Download → clique no botão que diz exatamente:",
        "smplx_step2b": "      'Download SMPL-X v1.1 (NPZ+PKL, 830 MB) - Use this for SMPL-X Python codebase'",
        "smplx_step3": "3.  Selecione o zip baixado abaixo (models_smplx_v1_1.zip).",
        "smpl_step1": "1.  Abra https://smpl.is.tue.mpg.de/  →  registre-se e faça login",
        "smpl_step2": "2.  Vá em Download → clique em:",
        "smpl_step2b": "      'Version 1.1.0 for Python 2.7 (female/male/neutral, 247 MB)'",
        "smpl_step3": "3.  Selecione o zip baixado abaixo (SMPL_python_v.1.1.0.zip).",
        "open_smplx_site": "🌐 Abrir site SMPL-X",
        "open_smpl_site": "🌐 Abrir site SMPL",
        "import_smplx_zip": "📦 Importar zip SMPL-X",
        "import_smpl_zip": "📦 Importar zip SMPL",
        "mano_step1": "1.  Abra https://mano.is.tue.mpg.de/  →  registre-se e faça login",
        "mano_step2": "2.  Vá em Download → clique no primeiro link:",
        "mano_step2b": "      'Models & Code (mano_v1_2.zip)'",
        "mano_step3": "3.  Selecione o zip baixado abaixo (mano_v1_2.zip).",
        "open_mano_site": "🌐 Abrir site MANO",
        "import_mano_zip": "📦 Importar zip MANO",
        "setup_title": "Instalação necessária",
        "setup_msg": "Alguns modelos ainda não estão instalados:\n\n  Obrigatórios (render do corpo): {req}\n  Mãos (opcional): {mano}\n\nUse os importadores desta página de Configurações para instalá-los. Depois de instalados, este aviso não aparecerá mais.",
        "check_gpu": "🎮 Verificar GPU",
        "open_proj": "📂 Abrir Pasta do Projeto",
        "uninstall": "🗑 Desinstalar / Liberar espaço",
        "console": "Saída do Console",
        "show_console": "Mostrar Console ▼",
        "hide_console": "Ocultar Console ▲",
        "ready": "Pronto",
        "running": "Executando: {0}...",
        "completed": "Concluído!",
        "failed": "Falhou (código {0})",
        "stopped": "Parado pelo usuário",
        "browse": "Procurar",
        "auto_detect": "Auto-detectar",
        "folder_hint": "Pasta com hmr4d_results.pt — exporta esqueleto Mixamo diretamente",
        "leave_empty": "(deixe vazio para automático)",
    },
}

# ═══════════════════════════════════════════════════════
# COLORES
# ═══════════════════════════════════════════════════════
class Colors:
    # Palette based on app icon — monochrome black/white/grey
    BG = "#080808"           # Main background — near black
    SIDEBAR = "#000000"      # Sidebar — pure black like icon background
    SURFACE = "#111111"      # Card surface
    CARD = "#1A1A1A"         # Inner cards / hover
    ACCENT = "#C0C0C0"       # Silver — primary buttons (figures on black)
    ACCENT_HOVER = "#E0E0E0" # Brighter silver on hover
    TEXT = "#FFFFFF"         # Pure white text
    TEXT_SECONDARY = "#B0B0B0"  # Light grey secondary text
    MUTED = "#666666"        # Medium grey
    BORDER = "#333333"       # Visible borders on dark surfaces
    SUCCESS = "#909090"      # Grey action buttons
    SUCCESS_HOVER = "#B0B0B0"
    ERROR = "#ef4444"
    ERROR_HOVER = "#f87171"
    WARNING = "#f59e0b"
    INPUT_BG = "#1A1A1A"
    INPUT_BORDER = "#444444"


# ═══════════════════════════════════════════════════════
# FASES DE PROGRESO GLOBAL
# ═══════════════════════════════════════════════════════
# Cada fase: (nombre, pct_inicio, pct_fin, keywords_detect)
# El parser detecta keywords en los logs para saber en qué fase está,
# y escala cualquier porcentaje local (ej. tqdm) al rango global.
PHASE_CONFIGS = {
    "pipeline.py": [
        ("init",       0.00, 0.05, ["[Input]", "[Output Dir]", "[Copy Video]", "[Preprocess] Start!"]),
        ("preprocess", 0.05, 0.20, ["[Preprocess]"]),
        ("predict",    0.20, 0.55, ["[HMR4D] Predicting"]),
        ("render",     0.55, 1.00, ["[Render Incam]", "[Render Global]", "Rendering Incam", "Rendering Global", "[Merge Videos]"]),
    ],
    "pipeline_fullbody.py": [
        ("step1_body",  0.00, 0.35, ["[Step 1/3]"]),
        ("step2_hands", 0.35, 0.70, ["[Step 2/3]", "HaMeR Hands"]),
        ("step3_render",0.70, 1.00, ["[Step 3/3]", "Rendering Incam+Hands", "Rendering Global+Hands"]),
    ],
    "default": [
        ("running", 0.00, 1.00, []),
    ],
}


# ═══════════════════════════════════════════════════════
# COMPONENTES
# ═══════════════════════════════════════════════════════
class Card(ctk.CTkFrame):
    def __init__(self, master, title: str = "", **kwargs):
        super().__init__(
            master,
            fg_color=Colors.SURFACE,
            corner_radius=12,
            border_width=1,
            border_color=Colors.BORDER,
            **kwargs,
        )
        if title:
            ctk.CTkLabel(
                self,
                text=title,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=Colors.ACCENT,
                anchor="w",
            ).pack(padx=20, pady=(16, 4), fill="x")
            ctk.CTkFrame(self, height=1, fg_color=Colors.BORDER).pack(padx=20, pady=(4, 0), fill="x")
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.pack(padx=20, pady=(12, 16), fill="both", expand=True)


class NavButton(ctk.CTkButton):
    def __init__(self, master, text: str, icon: str = "", selected: bool = False, **kwargs):
        super().__init__(
            master,
            text=f"  {icon}  {text}" if icon else text,
            font=ctk.CTkFont(size=13),
            height=42,
            corner_radius=10,
            anchor="w",
            fg_color=Colors.ACCENT if selected else "transparent",
            hover_color=Colors.CARD,
            text_color="#000000" if selected else Colors.MUTED,
            **kwargs,
        )

    def set_selected(self, selected: bool):
        self.configure(
            fg_color=Colors.ACCENT if selected else "transparent",
            text_color="#000000" if selected else Colors.MUTED,
        )


class Tooltip:
    """Tooltip flotante estilo moderno para CustomTkinter."""

    def __init__(self, widget, text: str, delay: int = 400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip_window = None
        self.id = None
        self.widget.bind("<Enter>", self._on_enter)
        self.widget.bind("<Leave>", self._on_leave)
        self.widget.bind("<ButtonPress>", self._on_leave)

    def _on_enter(self, _event=None):
        self.id = self.widget.after(self.delay, self._show)

    def _on_leave(self, _event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        self._hide()

    def _show(self):
        if self.tip_window or not self.text:
            return
        # Posicionar debajo del cursor
        x = self.widget.winfo_pointerx()
        y = self.widget.winfo_pointery() + 18
        self.tip_window = ctk.CTkToplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.configure(fg_color=Colors.CARD)
        self.tip_window.attributes("-topmost", True)
        self.tip_window.withdraw()

        label = ctk.CTkLabel(
            self.tip_window,
            text=self.text,
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY,
            fg_color=Colors.CARD,
            corner_radius=8,
            padx=12,
            pady=8,
        )
        label.pack()

        # Calcular tamaño y centrar horizontalmente respecto al cursor
        self.tip_window.update_idletasks()
        tw = self.tip_window.winfo_width()
        th = self.tip_window.winfo_height()
        sw = self.tip_window.winfo_screenwidth()
        sh = self.tip_window.winfo_screenheight()

        x = x - tw // 2
        # Si no cabe abajo, mostrar arriba del cursor
        if y + th + 10 > sh:
            y = self.widget.winfo_pointery() - th - 10
        # Ajustar horizontalmente para no salirse de la pantalla
        if x < 10:
            x = 10
        elif x + tw > sw - 10:
            x = sw - tw - 10

        self.tip_window.wm_geometry(f"+{x}+{y}")
        self.tip_window.deiconify()

    def _hide(self):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


# ═══════════════════════════════════════════════════════
# APP
# ═══════════════════════════════════════════════════════
class MocapOSApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("MocapOS — Motion Capture")
        self.geometry("1280x860")
        self.minsize(1000, 700)
        self.configure(fg_color=Colors.BG)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # ── App Icon ──
        icon_path = str(PROJ_ROOT / "assets" / "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
                # Show icon in Windows taskbar
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MocapOS.App")
            except Exception:
                pass

        self.process = None
        self.running = False
        self.lang = tk.StringVar(value=self._load_lang())

        # Progress phase tracking
        self.current_phases = PHASE_CONFIGS["default"]
        self.current_phase_idx = 0

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar ──
        self.sidebar = ctk.CTkFrame(
            self, width=260, fg_color=Colors.SIDEBAR,
            corner_radius=0, border_width=0,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Logo
        logo = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo.pack(padx=20, pady=(24, 8), fill="x")
        ctk.CTkLabel(logo, text="◆  MocapOS",
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=Colors.TEXT, anchor="w").pack(fill="x")
        ctk.CTkLabel(logo, text="Motion Capture System",
                     font=ctk.CTkFont(size=11),
                     text_color=Colors.MUTED, anchor="w").pack(fill="x", pady=(2, 0))

        ctk.CTkFrame(self.sidebar, height=1, fg_color=Colors.BORDER).pack(padx=20, pady=(8, 12), fill="x")

        # Nav (4 items only)
        self.nav_buttons = []
        self.nav_keys = [
            ("inference", "▶"),
            ("skeleton_transfer", "🦴"),
            ("export_bvh", "📤"),
            ("settings", "⚙"),
        ]
        self.page_builders = [
            self._show_inference_page,
            self._show_retarget_page,
            self._show_export_page,
            self._show_settings_page,
        ]
        self.current_page_index = -1

        for i, (key, icon) in enumerate(self.nav_keys):
            btn = NavButton(
                self.sidebar, text=self._t(key), icon=icon,
                selected=(i == 0),
                command=lambda idx=i: self.navigate(idx),
            )
            btn.pack(padx=16, pady=3, fill="x")
            self.nav_buttons.append(btn)

        ctk.CTkFrame(self.sidebar, height=1, fg_color=Colors.BORDER).pack(padx=20, pady=(16, 12), fill="x", side="top")

        self.status_var = tk.StringVar(value=self._t("ready"))
        self.status_label = ctk.CTkLabel(
            self.sidebar,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Colors.WARNING,
            anchor="w",
        )
        self.status_label.pack(padx=20, pady=(0, 8), fill="x", side="top")

        # Language selector
        lang_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        lang_frame.pack(padx=20, pady=(0, 16), fill="x", side="top")
        ctk.CTkLabel(lang_frame, text="🌐", font=ctk.CTkFont(size=14)).pack(side="left")
        self.lang_combo = ctk.CTkComboBox(
            lang_frame,
            values=[TRANSLATIONS["en"]["lang_name"], TRANSLATIONS["es"]["lang_name"],
                    TRANSLATIONS["fr"]["lang_name"], TRANSLATIONS["pt"]["lang_name"]],
            width=160,
            fg_color=Colors.INPUT_BG,
            border_color=Colors.INPUT_BORDER,
            button_color=Colors.INPUT_BORDER,
            dropdown_fg_color=Colors.INPUT_BG,
            dropdown_hover_color=Colors.CARD,
            text_color=Colors.TEXT,
            command=self._change_language,
        )
        self.lang_combo.set(TRANSLATIONS.get(self.lang.get(), TRANSLATIONS["en"])["lang_name"])
        self.lang_combo.pack(side="left", padx=(8, 0), fill="x", expand=True)

        # ── Content ──
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=28, pady=28)
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.current_page = None
        self._route_initial_page()

    def _route_initial_page(self):
        """First-run onboarding. If the REQUIRED body models are missing, open on the
        Settings page (model importers) and show a notice listing what's missing, so
        the user can install everything. Once installed, this stops and the app opens
        normally on the Inference page (no more warning)."""
        missing_required = []
        if not (PROJ_ROOT / "inputs/checkpoints/body_models/smplx/SMPLX_NEUTRAL.npz").exists():
            missing_required.append("SMPL-X")
        if not (PROJ_ROOT / "inputs/checkpoints/body_models/smpl/SMPL_NEUTRAL.pkl").exists():
            missing_required.append("SMPL")
        mano_missing = not (PROJ_ROOT / "hamer_lib/_DATA/data/mano/MANO_RIGHT.pkl").exists()

        if missing_required:
            self.navigate(3)  # Settings page holds the model importers
            req = ", ".join(missing_required)
            mano = "MANO ✗" if mano_missing else "OK ✓"
            self.after(350, lambda: messagebox.showwarning(
                self._t("setup_title"),
                self._t("setup_msg").format(req=req, mano=mano),
            ))
        else:
            self.navigate(0)  # everything required is installed -> normal start

    # ═══════════════════════════════════════════════════════
    def _t(self, key: str) -> str:
        return TRANSLATIONS.get(self.lang.get(), TRANSLATIONS["en"]).get(key, key)

    # ── Language persistence (remembered between sessions) ──────────────
    def _lang_path(self):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "MocapOS", "lang.txt")

    def _load_lang(self):
        try:
            with open(self._lang_path(), encoding="utf-8") as f:
                code = f.read().strip().lower()
                if code in TRANSLATIONS:
                    return code
        except Exception:
            pass
        return "en"

    def _save_lang(self):
        try:
            p = self._lang_path()
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.lang.get())
        except Exception:
            pass

    def _change_language(self, _value=None):
        name = self.lang_combo.get()
        for code, trans in TRANSLATIONS.items():
            if trans["lang_name"] == name:
                self.lang.set(code)
                break
        self._save_lang()
        # Update nav buttons text
        for i, (key, icon) in enumerate(self.nav_keys):
            self.nav_buttons[i].configure(text=f"  {icon}  {self._t(key)}")
        self.navigate(self.current_page_index, force=True)

    def navigate(self, index: int, force: bool = False):
        if not force and index == self.current_page_index:
            return
        for i, btn in enumerate(self.nav_buttons):
            btn.set_selected(i == index)
        if self.current_page is not None:
            self.current_page.destroy()
        self.current_page_index = index
        self.current_page = ctk.CTkScrollableFrame(
            self.content, fg_color="transparent", corner_radius=0
        )
        self.current_page.grid(row=0, column=0, sticky="nsew")
        self.page_builders[index](self.current_page)

    def _page_header(self, parent, title: str, subtitle: str):
        ctk.CTkLabel(parent, text=title,
                     font=ctk.CTkFont(size=24, weight="bold"),
                     text_color=Colors.TEXT, anchor="w").pack(padx=0, pady=(0, 4), fill="x")
        ctk.CTkLabel(parent, text=subtitle,
                     font=ctk.CTkFont(size=13),
                     text_color=Colors.MUTED, anchor="w").pack(padx=0, pady=(0, 20), fill="x")

    def _build_console(self, parent):
        # ── Progress Panel (always visible) ──
        prog_panel = ctk.CTkFrame(parent, fg_color=Colors.SURFACE, corner_radius=12, border_width=1, border_color=Colors.BORDER)
        prog_panel.pack(fill="x", pady=(0, 12))

        prog_inner = ctk.CTkFrame(prog_panel, fg_color="transparent")
        prog_inner.pack(fill="x", padx=20, pady=(16, 16))

        # Percentage + Status
        top_row = ctk.CTkFrame(prog_inner, fg_color="transparent")
        top_row.pack(fill="x")

        self.progress_pct_label = ctk.CTkLabel(
            top_row, text="0%",
            font=ctk.CTkFont(size=28, weight="bold"),
            text_color=Colors.ACCENT,
        )
        self.progress_pct_label.pack(side="left")

        self.progress_status_label = ctk.CTkLabel(
            top_row, text="",
            font=ctk.CTkFont(size=12),
            text_color=Colors.TEXT_SECONDARY,
        )
        self.progress_status_label.pack(side="left", padx=(12, 0))

        # Progress bar
        self.progress = ctk.CTkProgressBar(
            prog_inner, mode="determinate",
            progress_color=Colors.ACCENT,
            fg_color=Colors.CARD,
            height=8,
            corner_radius=4,
        )
        self.progress.pack(fill="x", pady=(10, 0))
        self.progress.set(0)

        # ── Console Toggle ──
        self.console_visible = False
        self.console_toggle_btn = ctk.CTkButton(
            parent,
            text=self._t("show_console"),
            fg_color="transparent",
            hover_color=Colors.CARD,
            text_color=Colors.MUTED,
            font=ctk.CTkFont(size=11),
            command=self._toggle_console,
            height=28,
            anchor="w",
        )
        self.console_toggle_btn.pack(fill="x", pady=(0, 4))

        # ── Console Frame (collapsible) ──
        self.console_frame = ctk.CTkFrame(parent, fg_color="transparent")

        log_card = Card(self.console_frame, title=self._t("console"))
        log_card.pack(fill="both", expand=True, pady=(0, 16))

        self.log_text = ctk.CTkTextbox(
            log_card.content_frame,
            font=ctk.CTkFont(family="Cascadia Code", size=11),
            fg_color=Colors.INPUT_BG,
            text_color=Colors.TEXT_SECONDARY,
            border_color=Colors.BORDER,
            corner_radius=8,
            wrap="word",
            height=180,
        )
        self.log_text.pack(fill="both", expand=True)

    def _toggle_console(self):
        self.console_visible = not self.console_visible
        if self.console_visible:
            self.console_frame.pack(fill="both", expand=True, pady=(8, 0))
            self.console_toggle_btn.configure(text=self._t("hide_console"))
        else:
            self.console_frame.pack_forget()
            self.console_toggle_btn.configure(text=self._t("show_console"))

    def _set_progress(self, value):
        """Update progress bar and percentage label. value: 0.0 - 1.0"""
        value = max(0.0, min(1.0, value))
        pct = int(value * 100)
        self.progress.set(value)
        self.progress_pct_label.configure(text=f"{pct}%")
        if value >= 1.0:
            self.progress_pct_label.configure(text_color=Colors.SUCCESS)
        elif value > 0:
            self.progress_pct_label.configure(text_color=Colors.ACCENT)
        else:
            self.progress_pct_label.configure(text_color=Colors.MUTED)

    def _parse_progress(self, text):
        """Parse log output to update global progress across pipeline phases."""
        if not self.current_phases:
            return

        # ── 1. Detect phase change by keywords ──
        phase_changed = False
        for idx, (name, start, end, keywords) in enumerate(self.current_phases):
            for kw in keywords:
                if kw in text:
                    if idx != self.current_phase_idx:
                        self.current_phase_idx = idx
                        phase_changed = True
                    break

        # If we changed phase, jump to phase start
        if phase_changed:
            start_pct = self.current_phases[self.current_phase_idx][1]
            self._set_progress(start_pct)
            return

        # ── 2. Extract local percentage from tqdm/output ──
        local_pct = None
        # Pattern: 50% or 50.5%
        m = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
        if m:
            try:
                local_pct = float(m.group(1)) / 100
            except ValueError:
                pass
        # Pattern: 5/10, frame 5/10, etc.
        if local_pct is None:
            m = re.search(r'(\d+)\s*/\s*(\d+)', text)
            if m:
                try:
                    num, den = int(m.group(1)), int(m.group(2))
                    if den > 0:
                        local_pct = num / den
                except ValueError:
                    pass
        # Pattern: "epoch 3/10"
        if local_pct is None:
            m = re.search(r'(?:epoch|step|frame|batch|iter|item)\s*(\d+)\s*/\s*(\d+)', text, re.IGNORECASE)
            if m:
                try:
                    num, den = int(m.group(1)), int(m.group(2))
                    if den > 0:
                        local_pct = num / den
                except ValueError:
                    pass

        # ── 3. Scale local percentage to global phase range ──
        if local_pct is not None:
            phase = self.current_phases[self.current_phase_idx]
            start, end = phase[1], phase[2]
            global_pct = start + (end - start) * local_pct
            self._set_progress(global_pct)

    # ═══════════════════════════════════════════════════════
    # INFERENCE
    # ═══════════════════════════════════════════════════════
    def _show_inference_page(self, parent):
        self._page_header(parent, self._t("inference"), self._t("inference_sub"))

        card = Card(parent, title=self._t("video_input"))
        card.pack(fill="x", pady=(0, 16))
        row = ctk.CTkFrame(card.content_frame, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=self._t("video_file"), font=ctk.CTkFont(size=13),
                     text_color=Colors.TEXT_SECONDARY, width=100, anchor="w").pack(side="left")
        self.video_path_var = tk.StringVar()
        ctk.CTkEntry(row, textvariable=self.video_path_var, height=36,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG).pack(side="left", padx=(8, 8), fill="x", expand=True)
        ctk.CTkButton(row, text=self._t("browse"), width=90, height=36,
                      fg_color=Colors.SUCCESS, hover_color=Colors.SUCCESS_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=self._browse_video).pack(side="left")

        card2 = Card(parent, title=self._t("output_dir"))
        card2.pack(fill="x", pady=(0, 16))
        row2 = ctk.CTkFrame(card2.content_frame, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        ctk.CTkLabel(row2, text=self._t("output"), font=ctk.CTkFont(size=13),
                     text_color=Colors.TEXT_SECONDARY, width=100, anchor="w").pack(side="left")
        self.output_dir_var = tk.StringVar(value="outputs/results")
        ctk.CTkEntry(row2, textvariable=self.output_dir_var, height=36,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG).pack(side="left", padx=(8, 8), fill="x", expand=True)
        ctk.CTkButton(row2, text=self._t("browse"), width=90, height=36,
                      fg_color=Colors.SUCCESS, hover_color=Colors.SUCCESS_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=self._browse_output).pack(side="left")

        card3 = Card(parent, title=self._t("options"))
        card3.pack(fill="x", pady=(0, 16))

        self.static_cam_var = tk.BooleanVar(value=False)
        self.use_dpvo_var = tk.BooleanVar(value=False)
        self.verbose_var = tk.BooleanVar(value=False)
        self.hands_var = tk.BooleanVar(value=False)
        self.use_focal_var = tk.BooleanVar(value=False)
        self.focal_var = tk.StringVar(value="24")

        sw_frame = ctk.CTkFrame(card3.content_frame, fg_color="transparent")
        sw_frame.pack(fill="x", pady=4)
        sw_frame.columnconfigure((0, 1), weight=1)

        sw_static = ctk.CTkSwitch(sw_frame, text=self._t("static_cam"), variable=self.static_cam_var,
                      progress_color=Colors.ACCENT, button_color=Colors.TEXT,
                      font=ctk.CTkFont(size=13))
        sw_static.grid(row=0, column=0, sticky="w", pady=6)
        Tooltip(sw_static, self._t("static_cam_tip"))
        sw_dpvo = ctk.CTkSwitch(sw_frame, text=self._t("use_dpvo"), variable=self.use_dpvo_var,
                      progress_color=Colors.ACCENT, button_color=Colors.TEXT,
                      font=ctk.CTkFont(size=13))
        sw_dpvo.grid(row=1, column=0, sticky="w", pady=6)
        Tooltip(sw_dpvo, self._t("use_dpvo_tip"))
        sw_verbose = ctk.CTkSwitch(sw_frame, text=self._t("verbose"), variable=self.verbose_var,
                      progress_color=Colors.ACCENT, button_color=Colors.TEXT,
                      font=ctk.CTkFont(size=13))
        sw_verbose.grid(row=2, column=0, sticky="w", pady=6)
        Tooltip(sw_verbose, self._t("verbose_tip"))
        sw_hands = ctk.CTkSwitch(sw_frame, text=self._t("hands"), variable=self.hands_var,
                      progress_color=Colors.ACCENT, button_color=Colors.TEXT,
                      font=ctk.CTkFont(size=13))
        sw_hands.grid(row=0, column=1, sticky="w", pady=6, padx=(20, 0))
        Tooltip(sw_hands, self._t("hands_tip"))

        focal = ctk.CTkFrame(card3.content_frame, fg_color="transparent")
        focal.pack(fill="x", pady=(12, 4))
        sw_focal = ctk.CTkSwitch(focal, text=self._t("focal"), variable=self.use_focal_var,
                      progress_color=Colors.ACCENT, button_color=Colors.TEXT,
                      font=ctk.CTkFont(size=13))
        sw_focal.pack(side="left")
        Tooltip(sw_focal, self._t("focal_tip"))
        ent_focal = ctk.CTkEntry(focal, textvariable=self.focal_var, width=70, height=32,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG)
        ent_focal.pack(side="left", padx=(12, 0))
        Tooltip(ent_focal, self._t("focal_entry_tip"))

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", pady=(4, 16))
        ctk.CTkButton(btn_row, text=self._t("run_inference"), height=44, width=160,
                      fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER,
                      text_color="#000000", font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._run_inference).pack(side="left", padx=(0, 12))
        ctk.CTkButton(btn_row, text=self._t("stop"), height=44, width=100,
                      fg_color=Colors.ERROR, hover_color=Colors.ERROR_HOVER,
                      text_color=Colors.TEXT, font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._stop_process).pack(side="left", padx=(0, 12))
        ctk.CTkButton(btn_row, text=self._t("open_output"), height=44, width=140,
                      fg_color=Colors.SUCCESS, hover_color=Colors.SUCCESS_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=self._open_output).pack(side="right")

        self._build_console(parent)

    # ═══════════════════════════════════════════════════════
    # EXPORT
    # ═══════════════════════════════════════════════════════
    def _show_export_page(self, parent):
        self._page_header(parent, self._t("export_bvh"), self._t("export_sub"))

        info = Card(parent, title="Info")
        info.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(info.content_frame, text=self._t("export_info"),
                     font=ctk.CTkFont(size=13), text_color=Colors.MUTED, anchor="w").pack(fill="x", pady=2)
        ctk.CTkLabel(info.content_frame, text=self._t("export_compat"),
                     font=ctk.CTkFont(size=13), text_color=Colors.MUTED, anchor="w").pack(fill="x", pady=2)

        card = Card(parent, title=self._t("results_dir"))
        card.pack(fill="x", pady=(0, 16))
        row = ctk.CTkFrame(card.content_frame, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=self._t("dir"), width=60, anchor="w", text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=13)).pack(side="left")
        self.export_dir_var = tk.StringVar()
        ent_edir = ctk.CTkEntry(row, textvariable=self.export_dir_var, height=36,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG)
        ent_edir.pack(side="left", padx=(8, 8), fill="x", expand=True)
        Tooltip(ent_edir, self._t("results_tip"))
        ctk.CTkButton(row, text=self._t("browse"), width=90, height=36,
                      fg_color=Colors.SUCCESS, hover_color=Colors.SUCCESS_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=lambda: self._browse_folder(self.export_dir_var)).pack(side="left")

        card2 = Card(parent, title=self._t("output_file"))
        card2.pack(fill="x", pady=(0, 16))
        row2 = ctk.CTkFrame(card2.content_frame, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        ctk.CTkLabel(row2, text=self._t("file"), width=60, anchor="w", text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=13)).pack(side="left")
        self.export_output_var = tk.StringVar()
        ent_eout = ctk.CTkEntry(row2, textvariable=self.export_output_var, height=36,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG)
        ent_eout.pack(side="left", padx=(8, 8), fill="x", expand=True)
        Tooltip(ent_eout, self._t("output_tip"))
        ctk.CTkButton(row2, text=self._t("browse"), width=90, height=36,
                      fg_color=Colors.SUCCESS, hover_color=Colors.SUCCESS_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=lambda: self._save_file(self.export_output_var, ext=".bvh",
                                                       filetypes=[["BVH", "*.bvh"]])).pack(side="left")
        ctk.CTkLabel(row2, text=self._t("leave_empty"), text_color=Colors.MUTED, font=ctk.CTkFont(size=12)).pack(side="left", padx=(8, 0))

        card3 = Card(parent, title=self._t("export_opts"))
        card3.pack(fill="x", pady=(0, 16))
        opts = ctk.CTkFrame(card3.content_frame, fg_color="transparent")
        opts.pack(fill="x", pady=4)
        self.export_body_only_var = tk.BooleanVar(value=False)
        sw_body = ctk.CTkSwitch(opts, text=self._t("body_only"),
                      variable=self.export_body_only_var,
                      progress_color=Colors.ACCENT, button_color=Colors.TEXT,
                      font=ctk.CTkFont(size=13))
        sw_body.pack(anchor="w", pady=6)
        Tooltip(sw_body, self._t("body_only_tip"))
        nums = ctk.CTkFrame(opts, fg_color="transparent")
        nums.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(nums, text=self._t("fps"), text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=13)).pack(side="left")
        self.export_fps_var = tk.StringVar(value="30")
        ent_efps = ctk.CTkEntry(nums, textvariable=self.export_fps_var, width=60, height=32,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG)
        ent_efps.pack(side="left", padx=(8, 20))
        Tooltip(ent_efps, self._t("fps_tip"))
        ctk.CTkLabel(nums, text=self._t("scale"), text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=13)).pack(side="left")
        self.export_scale_var = tk.StringVar(value="100")
        ent_escale = ctk.CTkEntry(nums, textvariable=self.export_scale_var, width=70, height=32,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG)
        ent_escale.pack(side="left", padx=(8, 12))
        Tooltip(ent_escale, self._t("scale_tip"))
        ctk.CTkLabel(nums, text="(100 = cm, 1 = meters)", text_color=Colors.MUTED, font=ctk.CTkFont(size=12)).pack(side="left")

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", pady=(4, 16))
        ctk.CTkButton(btn_row, text=self._t("export_bvh_btn"), height=44, width=160,
                      fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER,
                      text_color="#000000", font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._run_export).pack(side="left", padx=(0, 12))
        ctk.CTkButton(btn_row, text="⏹ Stop", height=44, width=100,
                      fg_color=Colors.ERROR, hover_color=Colors.ERROR_HOVER,
                      text_color=Colors.TEXT, font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._stop_process).pack(side="left")

        howto = Card(parent, title=self._t("howto_title"))
        howto.pack(fill="x", pady=(0, 16))
        for step in [
            "1. Run inference on your video (Inference tab)",
            "2. Export to BVH (this tab)",
            "3. Import BVH into your 3D software (Blender: File > Import > BVH)",
            "4. Retarget: map SMPL-X bones to your character's skeleton",
            "   • Blender: use Rokoko add-on or AutoRig Pro for auto retarget",
            "   • Unity: set imported FBX Rig to 'Humanoid', auto bone mapping",
            "   • Unreal: use IK Retargeter to map source to target skeleton",
        ]:
            ctk.CTkLabel(howto.content_frame, text=step, text_color=Colors.MUTED,
                         font=ctk.CTkFont(size=12)).pack(anchor="w", pady=2)

        self._build_console(parent)


    # ═══════════════════════════════════════════════════════
    # RETARGET (Skeleton Transfer)
    # ═══════════════════════════════════════════════════════
    def _show_retarget_page(self, parent):
        self._page_header(parent, self._t("skeleton_transfer"), self._t("skeleton_sub"))

        # Source
        src = Card(parent, title=self._t("anim_source"))
        src.pack(fill="x", pady=(0, 16))

        self.retarget_source_var = tk.StringVar(value="results")

        self.retarget_results_row = ctk.CTkFrame(src.content_frame, fg_color="transparent")
        self.retarget_results_row.pack(fill="x", pady=(6, 4))
        ctk.CTkLabel(self.retarget_results_row, text=self._t("results_folder"), width=110,
                     anchor="w", text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=13)).pack(side="left")
        self.retarget_results_var = tk.StringVar()
        ent_results = ctk.CTkEntry(self.retarget_results_row, textvariable=self.retarget_results_var, height=36,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG)
        ent_results.pack(side="left", padx=(8, 8), fill="x", expand=True)
        Tooltip(ent_results, self._t("results_folder_tip"))
        ctk.CTkButton(self.retarget_results_row, text=self._t("browse"), width=90, height=36,
                      fg_color=Colors.SUCCESS, hover_color=Colors.SUCCESS_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=lambda: self._browse_folder(self.retarget_results_var)).pack(side="left")
        ctk.CTkLabel(src.content_frame, text=self._t("folder_hint"),
                     text_color=Colors.MUTED, font=ctk.CTkFont(size=12), anchor="w").pack(fill="x", padx=8)

        # Character
        char = Card(parent, title=self._t("char"))
        char.pack(fill="x", pady=(0, 16))
        row2 = ctk.CTkFrame(char.content_frame, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        ctk.CTkLabel(row2, text=self._t("file"), width=60, anchor="w", text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=13)).pack(side="left")
        self.retarget_char_var = tk.StringVar()
        ent_char = ctk.CTkEntry(row2, textvariable=self.retarget_char_var, height=36,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG)
        ent_char.pack(side="left", padx=(8, 8), fill="x", expand=True)
        Tooltip(ent_char, self._t("char_tip"))
        ctk.CTkButton(row2, text=self._t("browse"), width=90, height=36,
                      fg_color=Colors.SUCCESS, hover_color=Colors.SUCCESS_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=lambda: self._browse_retarget_file(
                          self.retarget_char_var,
                          [["FBX / Collada", "*.fbx *.dae"], ["All files", "*.*"]]
                      )).pack(side="left")
        ctk.CTkLabel(row2, text=self._t("char_format"),
                     text_color=Colors.MUTED, font=ctk.CTkFont(size=12)).pack(side="left", padx=(8, 0))
        warn = ctk.CTkFrame(char.content_frame, fg_color="transparent")
        warn.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(warn, text=self._t("char_warn"),
                     text_color=Colors.ERROR, font=ctk.CTkFont(size=11, slant="italic")).pack(side="left")

        # Blender
        blend = Card(parent, title=self._t("blender"))
        blend.pack(fill="x", pady=(0, 16))
        row3 = ctk.CTkFrame(blend.content_frame, fg_color="transparent")
        row3.pack(fill="x", pady=4)
        ctk.CTkLabel(row3, text=self._t("blender_exe"), width=80, anchor="w", text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=13)).pack(side="left")
        self.retarget_blender_var = tk.StringVar(value=self._detect_blender())
        ent_blend = ctk.CTkEntry(row3, textvariable=self.retarget_blender_var, height=36,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG)
        ent_blend.pack(side="left", padx=(8, 8), fill="x", expand=True)
        Tooltip(ent_blend, self._t("blender_tip"))
        ctk.CTkButton(row3, text=self._t("browse"), width=90, height=36,
                      fg_color=Colors.SUCCESS, hover_color=Colors.SUCCESS_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=lambda: self._browse_retarget_file(
                          self.retarget_blender_var,
                          [["Blender", "blender.exe"], ["All files", "*.*"]]
                      )).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row3, text=self._t("auto_detect"), width=100, height=36,
                      fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=self._autodetect_blender).pack(side="left")

        # Export options
        ex = Card(parent, title=self._t("export_opts"))
        ex.pack(fill="x", pady=(0, 16))
        exin = ctk.CTkFrame(ex.content_frame, fg_color="transparent")
        exin.pack(fill="x", pady=4)

        fmt_row = ctk.CTkFrame(exin, fg_color="transparent")
        fmt_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(fmt_row, text=self._t("format"), text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=13)).pack(side="left")
        self.retarget_format_var = tk.StringVar(value="FBX")
        cb_fmt = ctk.CTkComboBox(fmt_row, values=["FBX", "GLB", "GLTF", "ABC", "DAE"],
                        variable=self.retarget_format_var, width=90, height=32,
                        fg_color=Colors.INPUT_BG, border_color=Colors.INPUT_BORDER,
                        button_color=Colors.INPUT_BORDER,
                        dropdown_fg_color=Colors.INPUT_BG,
                        dropdown_hover_color=Colors.CARD,
                        text_color=Colors.TEXT,
                        command=self._on_retarget_format_change)
        cb_fmt.pack(side="left", padx=(8, 20))
        Tooltip(cb_fmt, self._t("format_tip"))
        ctk.CTkLabel(fmt_row, text=self._t("fps"), text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=13)).pack(side="left")
        self.retarget_fps_var = tk.StringVar(value="30")
        ent_fps = ctk.CTkEntry(fmt_row, textvariable=self.retarget_fps_var, width=60, height=32,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG)
        ent_fps.pack(side="left", padx=(8, 0))
        Tooltip(ent_fps, self._t("retarget_fps_tip"))

        out_row = ctk.CTkFrame(exin, fg_color="transparent")
        out_row.pack(fill="x", pady=(8, 0))
        ctk.CTkLabel(out_row, text=self._t("output"), width=60, anchor="w", text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=13)).pack(side="left")
        self.retarget_output_var = tk.StringVar()
        ent_out = ctk.CTkEntry(out_row, textvariable=self.retarget_output_var, height=36,
                     border_color=Colors.INPUT_BORDER, fg_color=Colors.INPUT_BG)
        ent_out.pack(side="left", padx=(8, 8), fill="x", expand=True)
        Tooltip(ent_out, self._t("out_path_tip"))
        ctk.CTkButton(out_row, text=self._t("browse"), width=90, height=36,
                      fg_color=Colors.SUCCESS, hover_color=Colors.SUCCESS_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=self._browse_retarget_output).pack(side="left")

        # Buttons
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", pady=(4, 16))
        ctk.CTkButton(btn_row, text=self._t("transfer_btn"), height=44, width=180,
                      fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER,
                      text_color="#000000", font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._run_retarget).pack(side="left", padx=(0, 12))
        ctk.CTkButton(btn_row, text="⏹ Stop", height=44, width=100,
                      fg_color=Colors.ERROR, hover_color=Colors.ERROR_HOVER,
                      text_color=Colors.TEXT, font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._stop_process).pack(side="left")

        # Info
        info = Card(parent, title=self._t("how_works"))
        info.pack(fill="x", pady=(0, 16))
        for step in [
            self._t("workflow_1"),
            self._t("workflow_2"),
            self._t("workflow_3"),
            self._t("workflow_4"),
            "",
            self._t("workflow_5"),
        ]:
            ctk.CTkLabel(info.content_frame, text=step, text_color=Colors.MUTED,
                         font=ctk.CTkFont(size=12)).pack(anchor="w", pady=1)

        self._build_console(parent)

    # ═══════════════════════════════════════════════════════
    # SETTINGS
    # ═══════════════════════════════════════════════════════
    def _show_settings_page(self, parent):
        self._page_header(parent, self._t("settings"), self._t("settings_sub"))

        env = Card(parent, title=self._t("env"))
        env.pack(fill="x", pady=(0, 16))
        info = ctk.CTkFrame(env.content_frame, fg_color="transparent")
        info.pack(fill="x", pady=4)
        for label, value in [
            ("Project Root:", str(PROJ_ROOT)),
            ("Conda Env:", ENV_NAME),
            ("Python:", "3.10 (conda)"),
        ]:
            row = ctk.CTkFrame(info, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=label, text_color=Colors.ACCENT,
                         font=ctk.CTkFont(size=13, weight="bold"), width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"  {value}", text_color=Colors.TEXT_SECONDARY,
                         font=ctk.CTkFont(size=13)).pack(side="left")

        ckpt = Card(parent, title=self._t("checkpoints"))
        ckpt.pack(fill="x", pady=(0, 16))
        ckpt_inner = ctk.CTkFrame(ckpt.content_frame, fg_color="transparent")
        ckpt_inner.pack(fill="x", pady=4)

        checkpoints = {
            "GVHMR": "inputs/checkpoints/gvhmr/gvhmr_siga24_release.ckpt",
            "HMR2": "inputs/checkpoints/hmr2/epoch=10-step=25000.ckpt",
            "ViTPose": "inputs/checkpoints/vitpose/vitpose-h-multi-coco.pth",
            "YOLO v8x": "inputs/checkpoints/yolo/yolov8x.pt",
            "DPVO": "inputs/checkpoints/dpvo/dpvo.pth",
            "SMPLX Neutral": "inputs/checkpoints/body_models/smplx/SMPLX_NEUTRAL.npz",
            "SMPL Neutral": "inputs/checkpoints/body_models/smpl/SMPL_NEUTRAL.pkl",
            "HaMeR": "hamer_lib/_DATA/hamer_ckpts/checkpoints/hamer.ckpt",
            "MANO Right (hands)": "hamer_lib/_DATA/data/mano/MANO_RIGHT.pkl",
            "MANO Left (hands)": "hamer_lib/_DATA/data/mano/MANO_LEFT.pkl",
        }
        for name, path in checkpoints.items():
            row = ctk.CTkFrame(ckpt_inner, fg_color="transparent")
            row.pack(fill="x", pady=1)
            full = PROJ_ROOT / path
            status = "OK" if full.exists() else "MISSING"
            color = Colors.SUCCESS if full.exists() else Colors.ERROR
            ctk.CTkLabel(row, text=f"[{status}]", text_color=color,
                         font=ctk.CTkFont(size=12, weight="bold"), width=70, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"  {name}", font=ctk.CTkFont(size=13), text_color=Colors.TEXT_SECONDARY).pack(side="left")
            ctk.CTkLabel(row, text=f"  ({path})", text_color=Colors.MUTED,
                         font=ctk.CTkFont(size=11)).pack(side="left")

        # ── Body Models Importer ──
        body = Card(parent, title=self._t("body_models"))
        body.pack(fill="x", pady=(0, 16))
        body_inner = ctk.CTkFrame(body.content_frame, fg_color="transparent")
        body_inner.pack(fill="x", pady=4)

        ctk.CTkLabel(body_inner, text=self._t("body_models_intro"),
                     text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=12),
                     wraplength=900, justify="left", anchor="w").pack(fill="x", pady=(0, 14))

        # SMPL-X subsection
        smplx_frame = ctk.CTkFrame(body_inner, fg_color=Colors.INPUT_BG, corner_radius=8)
        smplx_frame.pack(fill="x", pady=(0, 10))
        smplx_path = PROJ_ROOT / "inputs/checkpoints/body_models/smplx/SMPLX_NEUTRAL.npz"
        smplx_status = "[OK]" if smplx_path.exists() else "[MISSING]"
        smplx_color = Colors.SUCCESS if smplx_path.exists() else Colors.ERROR
        ctk.CTkLabel(smplx_frame, text=f"  SMPL-X  {smplx_status}",
                     text_color=smplx_color, font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(fill="x", padx=12, pady=(10, 4))
        for key in ("smplx_step1", "smplx_step2", "smplx_step2b", "smplx_step3"):
            ctk.CTkLabel(smplx_frame, text=self._t(key),
                         text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=12),
                         anchor="w", justify="left").pack(fill="x", padx=14, pady=1)
        smplx_btn_row = ctk.CTkFrame(smplx_frame, fg_color="transparent")
        smplx_btn_row.pack(fill="x", padx=12, pady=(8, 12))
        ctk.CTkButton(smplx_btn_row, text=self._t("open_smplx_site"), height=36, width=180,
                      fg_color=Colors.MUTED, hover_color=Colors.BORDER,
                      command=lambda: webbrowser.open("https://smpl-x.is.tue.mpg.de/download.php")
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(smplx_btn_row, text=self._t("import_smplx_zip"), height=36, width=200,
                      fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=self._import_smplx_zip).pack(side="left")

        # SMPL subsection
        smpl_frame = ctk.CTkFrame(body_inner, fg_color=Colors.INPUT_BG, corner_radius=8)
        smpl_frame.pack(fill="x", pady=(0, 4))
        smpl_path = PROJ_ROOT / "inputs/checkpoints/body_models/smpl/SMPL_NEUTRAL.pkl"
        smpl_status = "[OK]" if smpl_path.exists() else "[MISSING]"
        smpl_color = Colors.SUCCESS if smpl_path.exists() else Colors.ERROR
        ctk.CTkLabel(smpl_frame, text=f"  SMPL  {smpl_status}",
                     text_color=smpl_color, font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(fill="x", padx=12, pady=(10, 4))
        for key in ("smpl_step1", "smpl_step2", "smpl_step2b", "smpl_step3"):
            ctk.CTkLabel(smpl_frame, text=self._t(key),
                         text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=12),
                         anchor="w", justify="left").pack(fill="x", padx=14, pady=1)
        smpl_btn_row = ctk.CTkFrame(smpl_frame, fg_color="transparent")
        smpl_btn_row.pack(fill="x", padx=12, pady=(8, 12))
        ctk.CTkButton(smpl_btn_row, text=self._t("open_smpl_site"), height=36, width=180,
                      fg_color=Colors.MUTED, hover_color=Colors.BORDER,
                      command=lambda: webbrowser.open("https://smpl.is.tue.mpg.de/download.php")
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(smpl_btn_row, text=self._t("import_smpl_zip"), height=36, width=200,
                      fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=self._import_smpl_zip).pack(side="left")

        # MANO subsection (hands)
        mano_frame = ctk.CTkFrame(body_inner, fg_color=Colors.INPUT_BG, corner_radius=8)
        mano_frame.pack(fill="x", pady=(10, 4))
        mano_path = PROJ_ROOT / "hamer_lib/_DATA/data/mano/MANO_RIGHT.pkl"
        mano_status = "[OK]" if mano_path.exists() else "[MISSING]"
        mano_color = Colors.SUCCESS if mano_path.exists() else Colors.ERROR
        ctk.CTkLabel(mano_frame, text=f"  MANO (hands)  {mano_status}",
                     text_color=mano_color, font=ctk.CTkFont(size=14, weight="bold"),
                     anchor="w").pack(fill="x", padx=12, pady=(10, 4))
        for key in ("mano_step1", "mano_step2", "mano_step2b", "mano_step3"):
            ctk.CTkLabel(mano_frame, text=self._t(key),
                         text_color=Colors.TEXT_SECONDARY, font=ctk.CTkFont(size=12),
                         anchor="w", justify="left").pack(fill="x", padx=14, pady=1)
        mano_btn_row = ctk.CTkFrame(mano_frame, fg_color="transparent")
        mano_btn_row.pack(fill="x", padx=12, pady=(8, 12))
        ctk.CTkButton(mano_btn_row, text=self._t("open_mano_site"), height=36, width=180,
                      fg_color=Colors.MUTED, hover_color=Colors.BORDER,
                      command=lambda: webbrowser.open("https://mano.is.tue.mpg.de/download.php")
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(mano_btn_row, text=self._t("import_mano_zip"), height=36, width=200,
                      fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=self._import_mano_zip).pack(side="left")

        btn = ctk.CTkFrame(parent, fg_color="transparent")
        btn.pack(fill="x", pady=(4, 16))
        ctk.CTkButton(btn, text=self._t("check_gpu"), height=44, width=160,
                      fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER,
                      text_color="#000000", font=ctk.CTkFont(size=14, weight="bold"),
                      command=self._check_gpu).pack(side="left", padx=(0, 12))
        ctk.CTkButton(btn, text=self._t("open_proj"), height=44, width=180,
                      fg_color=Colors.SUCCESS, hover_color=Colors.SUCCESS_HOVER,
                      text_color="#000000", font=ctk.CTkFont(weight="bold"),
                      command=lambda: os.startfile(str(PROJ_ROOT))).pack(side="left")
        ctk.CTkButton(btn, text=self._t("uninstall"), height=44, width=200,
                      fg_color=Colors.MUTED, hover_color=Colors.ERROR,
                      text_color=Colors.TEXT, font=ctk.CTkFont(weight="bold"),
                      command=self._uninstall).pack(side="left", padx=(12, 0))

        self._build_console(parent)

    def _uninstall(self):
        bat = PROJ_ROOT / "uninstall.bat"
        if not bat.exists():
            messagebox.showerror("Uninstall", "uninstall.bat was not found in the project folder.")
            return
        if messagebox.askyesno(
            "Uninstall / Free space",
            "This opens the uninstaller in a new window, with two options:\n\n"
            "   1) Free up space  - delete the portable environment + downloads,\n"
            "        keep your code and models.\n"
            "   2) Full uninstall - remove everything.\n\n"
            "Tip: close MocapOS first so all files can be removed.\n\n"
            "Open the uninstaller now?"
        ):
            os.startfile(str(bat))

    # ═══════════════════════════════════════════════════════
    # BODY MODEL IMPORTERS
    # ═══════════════════════════════════════════════════════
    def _import_mano_zip(self):
        path = filedialog.askopenfilename(
            title="Select MANO zip (mano_v1_2.zip)",
            filetypes=[["Zip files", "*.zip"], ["All files", "*.*"]],
        )
        if not path:
            return
        target_dir = PROJ_ROOT / "hamer_lib" / "_DATA" / "data" / "mano"
        target_dir.mkdir(parents=True, exist_ok=True)
        wanted = {"mano_left.pkl": "MANO_LEFT.pkl",
                  "mano_right.pkl": "MANO_RIGHT.pkl"}
        extracted = []
        try:
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    base = os.path.basename(info.filename).lower()
                    if base in wanted and wanted[base] not in extracted:
                        dest = target_dir / wanted[base]
                        with z.open(info) as src, open(dest, "wb") as out:
                            shutil.copyfileobj(src, out)
                        extracted.append(wanted[base])
        except zipfile.BadZipFile:
            messagebox.showerror("Invalid zip",
                "The selected file is not a valid zip. Please pick the file "
                "you downloaded from mano.is.tue.mpg.de.")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import MANO:\n{e}")
            return

        if extracted:
            messagebox.showinfo(
                "MANO imported",
                "Extracted:\n  - " + "\n  - ".join(extracted) +
                f"\n\nDestination: {target_dir}"
            )
            self.navigate(self.current_page_index, force=True)
        else:
            messagebox.showerror(
                "MANO files not found",
                "No MANO_LEFT.pkl / MANO_RIGHT.pkl found inside the zip.\n\n"
                "Make sure you downloaded the first link:\n"
                "  'Models & Code (mano_v1_2.zip)'\n\n"
                "on https://mano.is.tue.mpg.de/download.php"
            )

    def _import_smplx_zip(self):
        path = filedialog.askopenfilename(
            title="Select SMPL-X v1.1 zip (models_smplx_v1_1.zip)",
            filetypes=[["Zip files", "*.zip"], ["All files", "*.*"]],
        )
        if not path:
            return
        target_dir = PROJ_ROOT / "inputs" / "checkpoints" / "body_models" / "smplx"
        target_dir.mkdir(parents=True, exist_ok=True)
        wanted = {"smplx_neutral.npz": "SMPLX_NEUTRAL.npz",
                  "smplx_male.npz":    "SMPLX_MALE.npz",
                  "smplx_female.npz":  "SMPLX_FEMALE.npz"}
        extracted = []
        try:
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    base = os.path.basename(info.filename).lower()
                    if base in wanted and wanted[base] not in extracted:
                        dest = target_dir / wanted[base]
                        with z.open(info) as src, open(dest, "wb") as out:
                            shutil.copyfileobj(src, out)
                        extracted.append(wanted[base])
        except zipfile.BadZipFile:
            messagebox.showerror("Invalid zip",
                "The selected file is not a valid zip. Please pick the file "
                "you downloaded from smpl-x.is.tue.mpg.de.")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import SMPL-X:\n{e}")
            return

        if extracted:
            messagebox.showinfo(
                "SMPL-X imported",
                "Extracted:\n  - " + "\n  - ".join(extracted) +
                f"\n\nDestination: {target_dir}"
            )
            self.navigate(self.current_page_index, force=True)
        else:
            messagebox.showerror(
                "SMPL-X files not found",
                "No SMPLX_NEUTRAL.npz / MALE / FEMALE found inside the zip.\n\n"
                "Make sure you clicked the button labelled:\n"
                "  'Download SMPL-X v1.1 (NPZ+PKL, 830 MB) -\n"
                "   Use this for SMPL-X Python codebase'\n\n"
                "on https://smpl-x.is.tue.mpg.de/download.php"
            )

    def _import_smpl_zip(self):
        path = filedialog.askopenfilename(
            title="Select SMPL zip (SMPL_python_v.1.1.0.zip)",
            filetypes=[["Zip files", "*.zip"], ["All files", "*.*"]],
        )
        if not path:
            return
        target_dir = PROJ_ROOT / "inputs" / "checkpoints" / "body_models" / "smpl"
        target_dir.mkdir(parents=True, exist_ok=True)

        def classify(name_lower: str):
            if not name_lower.endswith(".pkl"):
                return None
            if "neutral" in name_lower:
                return "SMPL_NEUTRAL.pkl"
            # SMPL v1.1.0 zip uses _m_ and _f_ tokens
            if "_m_" in name_lower or "_male_" in name_lower or "male" in name_lower:
                return "SMPL_MALE.pkl"
            if "_f_" in name_lower or "_female_" in name_lower or "female" in name_lower:
                return "SMPL_FEMALE.pkl"
            return None

        extracted = []
        try:
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    base = os.path.basename(info.filename).lower()
                    if not base.startswith(("basicmodel", "smpl_", "smpl ")):
                        continue
                    canonical = classify(base)
                    if not canonical or canonical in extracted:
                        continue
                    dest = target_dir / canonical
                    with z.open(info) as src, open(dest, "wb") as out:
                        shutil.copyfileobj(src, out)
                    extracted.append(canonical)
        except zipfile.BadZipFile:
            messagebox.showerror("Invalid zip",
                "The selected file is not a valid zip. Please pick the file "
                "you downloaded from smpl.is.tue.mpg.de.")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import SMPL:\n{e}")
            return

        if extracted:
            messagebox.showinfo(
                "SMPL imported",
                "Extracted and renamed:\n  - " + "\n  - ".join(extracted) +
                f"\n\nDestination: {target_dir}"
            )
            self.navigate(self.current_page_index, force=True)
        else:
            messagebox.showerror(
                "SMPL files not found",
                "No basicmodel_*.pkl files found inside the zip.\n\n"
                "Make sure you clicked the button labelled:\n"
                "  'Version 1.1.0 for Python 2.7\n"
                "   (female/male/neutral, 247 MB)'\n\n"
                "on https://smpl.is.tue.mpg.de/download.php"
            )


    # ═══════════════════════════════════════════════════════
    # HELPERS / BROWSERS
    # ═══════════════════════════════════════════════════════
    def _browse_video(self):
        path = filedialog.askopenfilename(
            title="Select Video",
            filetypes=[["Video files", "*.mp4 *.avi *.mov *.mkv *.MP4"], ["All files", "*.*"]]
        )
        if path:
            self.video_path_var.set(os.path.normpath(path))

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_dir_var.set(os.path.normpath(path))

    def _browse_folder(self, var):
        path = filedialog.askdirectory(title="Select Folder")
        if path:
            var.set(os.path.normpath(path))

    def _browse_file(self, var):
        path = filedialog.askopenfilename(filetypes=[["Video files", "*.mp4 *.avi *.mov"], ["All", "*.*"]])
        if path:
            var.set(os.path.normpath(path))

    def _save_file(self, var, ext=".mp4", filetypes=None):
        if filetypes is None:
            filetypes = [["MP4", "*.mp4"]]
        path = filedialog.asksaveasfilename(defaultextension=ext, filetypes=filetypes)
        if path:
            var.set(os.path.normpath(path))

    def _browse_retarget_file(self, var, filetypes):
        path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            var.set(os.path.normpath(path))

    def _browse_retarget_output(self):
        fmt = self.retarget_format_var.get().upper()
        ext_map = {"FBX": ".fbx", "GLB": ".glb", "GLTF": ".gltf", "ABC": ".abc", "DAE": ".dae"}
        ext = ext_map.get(fmt, ".fbx")
        filetypes = [[f"{fmt} file", f"*{ext}"], ["All files", "*.*"]]
        path = filedialog.asksaveasfilename(defaultextension=ext, filetypes=filetypes)
        if path:
            self.retarget_output_var.set(os.path.normpath(path))

    def _on_retarget_source_change(self):
        mode = self.retarget_source_var.get()
        if mode == "bvh":
            self.retarget_results_row.pack_forget()
            self.retarget_bvh_row.pack(fill="x", pady=(6, 4))
        else:
            self.retarget_bvh_row.pack_forget()
            self.retarget_results_row.pack(fill="x", pady=(6, 4))

    def _on_retarget_format_change(self, _event=None):
        current = self.retarget_output_var.get().strip()
        if not current:
            return
        fmt = self.retarget_format_var.get().lower()
        new_path = str(Path(current).with_suffix(f".{fmt}"))
        self.retarget_output_var.set(new_path)

    def _log(self, text):
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self._parse_progress(text)

    def _clear_log(self):
        self.log_text.delete("1.0", "end")

    def _set_status(self, text, color=Colors.WARNING):
        self.status_var.set(text)
        self.status_label.configure(text_color=color)

    # ═══════════════════════════════════════════════════════
    # PROCESS RUNNERS
    # ═══════════════════════════════════════════════════════
    def _run_command(self, args, label="Process", on_success=None):
        if self.running:
            messagebox.showwarning("Busy", "A process is already running. Stop it first.")
            return

        self._clear_log()
        self.running = True
        self._set_status(self._t("running").format(label))

        # Detect script to pick correct phase config
        script_name = Path(args[0]).name if args else "default"
        self.current_phases = PHASE_CONFIGS.get(script_name, PHASE_CONFIGS["default"])
        self.current_phase_idx = 0

        python_exe = _env_python()
        cmd = [python_exe, "-u"] + args
        cmd_str = " ".join(args)
        self._log(f"=== {label} ===\n")
        self._log(f"Working dir: {PROJ_ROOT}\n")
        self._log(f"Command: python -u {cmd_str}\n")
        self._log(f"{'=' * 60}\n\n")
        self._set_progress(0)
        self.after(0, lambda: self.progress_status_label.configure(text=self._t("running").format(label)))

        def worker():
            success = False
            try:
                env = os.environ.copy()
                conda_env = str(ENV_DIR)
                env["CONDA_DEFAULT_ENV"] = ENV_NAME
                env["CONDA_PREFIX"] = conda_env
                env["PATH"] = (
                    conda_env + ";" +
                    os.path.join(conda_env, "Scripts") + ";" +
                    os.path.join(conda_env, "Library", "bin") + ";" +
                    env.get("PATH", "")
                )

                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(PROJ_ROOT),
                    env=env,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

                for line in iter(self.process.stdout.readline, ""):
                    if line:
                        self.after(0, self._log, line)

                self.process.wait()
                rc = self.process.returncode

                self.after(0, self._log, f"\n{'=' * 60}\n")
                if rc == 0:
                    success = True
                    self.after(0, self._log, f"=== COMPLETED SUCCESSFULLY ===\n")
                    self.after(0, self._set_status, self._t("completed"), Colors.SUCCESS)
                    if on_success:
                        self.after(500, on_success)
                    else:
                        self.after(0, lambda: messagebox.showinfo("Done", f"{label} completed successfully!"))
                else:
                    self.after(0, self._log, f"=== FAILED (exit code: {rc}) ===\n")
                    self.after(0, self._set_status, self._t("failed").format(rc), Colors.ERROR)
                    self.after(0, lambda: messagebox.showerror(
                        "Error",
                        f"{label} failed with exit code {rc}.\n\nCheck the Console Output for details."
                    ))
            except FileNotFoundError:
                msg = (
                    f"Could not find Python at:\n{python_exe}\n\n"
                    f"Make sure the conda environment '{ENV_NAME}' is set up correctly."
                )
                self.after(0, self._log, f"\nERROR: {msg}\n")
                self.after(0, lambda: messagebox.showerror("Python Not Found", msg))
                self.after(0, self._set_status, "Error: Python not found", Colors.ERROR)
            except Exception as e:
                self.after(0, self._log, f"\nUnexpected Error: {type(e).__name__}: {e}\n")
                self.after(0, self._set_status, f"Error: {e}", Colors.ERROR)
            finally:
                self.after(0, lambda: self._set_progress(1.0 if success else 0))
                self.after(0, lambda: self.progress_status_label.configure(text=""))
                self.running = False
                self.process = None

        threading.Thread(target=worker, daemon=True).start()

    def _run_blender_command(self, cmd, label="Blender"):
        if self.running:
            messagebox.showwarning("Busy", "A process is already running. Stop it first.")
            return

        self._clear_log()
        self.running = True
        self._set_status(self._t("running").format(label))

        self.current_phases = PHASE_CONFIGS["default"]
        self.current_phase_idx = 0

        self._log(f"=== {label} ===\n")
        self._log(f"Command: {' '.join(cmd[:3])} --background --python ... --\n")
        self._log(f"{'=' * 60}\n\n")
        self._set_progress(0)
        self.after(0, lambda: self.progress_status_label.configure(text=self._t("running").format(label)))

        def worker():
            success = False
            try:
                self.process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )

                for line in iter(self.process.stdout.readline, ""):
                    if line:
                        self.after(0, self._log, line)

                self.process.wait()
                rc = self.process.returncode

                self.after(0, self._log, f"\n{'=' * 60}\n")
                if rc == 0:
                    success = True
                    self.after(0, self._log, "=== COMPLETED SUCCESSFULLY ===\n")
                    self.after(0, self._set_status, self._t("completed"), Colors.SUCCESS)
                    output = self.retarget_output_var.get().strip()
                    self.after(0, lambda: messagebox.showinfo(
                        "Done!",
                        f"Transfer completed!\n\nExported file:\n{output}"
                    ))
                else:
                    self.after(0, self._log, f"=== FAILED (exit code: {rc}) ===\n")
                    self.after(0, self._set_status, self._t("failed").format(rc), Colors.ERROR)
                    self.after(0, lambda: messagebox.showerror(
                        "Error",
                        f"{label} failed with exit code {rc}.\n\nCheck the Console Output."
                    ))
            except FileNotFoundError:
                msg = f"Blender not found at:\n{cmd[0]}"
                self.after(0, self._log, f"\nERROR: {msg}\n")
                self.after(0, lambda: messagebox.showerror("Blender Not Found", msg))
                self.after(0, self._set_status, "Error: Blender not found", Colors.ERROR)
            except Exception as e:
                self.after(0, self._log, f"\nUnexpected Error: {type(e).__name__}: {e}\n")
                self.after(0, self._set_status, f"Error: {e}", Colors.ERROR)
            finally:
                self.after(0, lambda: self._set_progress(1.0 if success else 0))
                self.after(0, lambda: self.progress_status_label.configure(text=""))
                self.running = False
                self.process = None

        threading.Thread(target=worker, daemon=True).start()

    def _stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self._log("\n=== Process terminated by user ===\n")
            self._set_progress(0)
            self.progress_status_label.configure(text="")
            self._set_status(self._t("stopped"), Colors.ERROR)
            self.running = False
        else:
            self._log("No process running.\n")

    def _fix_video_rotation(self, video_path):
        try:
            ffprobe = _env_tool("ffprobe")
            if not ffprobe:
                self._log("Warning: ffprobe not found. Skipping rotation check.\n")
                return video_path
            result = subprocess.run(
                [ffprobe, "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-show_format", video_path],
                capture_output=True, text=True
            )
            import json
            data = json.loads(result.stdout)

            needs_fix = False
            reason = ""

            if video_path.lower().endswith('.mov'):
                needs_fix = True
                reason = "MOV file (phone recording)"

            for stream in data.get("streams", []):
                if stream.get("codec_type") != "video":
                    continue
                rotation = stream.get("tags", {}).get("rotate", "0")
                if rotation != "0":
                    needs_fix = True
                    reason = f"rotation tag: {rotation} deg"
                for sd in stream.get("side_data_list", []):
                    sd_type = sd.get("side_data_type", "")
                    if "display" in sd_type.lower() or "rotation" in sd_type.lower():
                        rot = sd.get("rotation", 0)
                        if rot != 0:
                            needs_fix = True
                            reason = f"display rotation: {rot} deg"
                w = int(stream.get("width", 0))
                h = int(stream.get("height", 0))
                if w > 0 and h > 0 and h > w:
                    needs_fix = True
                    reason = f"portrait video ({w}x{h})"

            if needs_fix:
                fixed_path = str(Path(video_path).with_suffix("")) + "_fixed.mp4"
                if os.path.exists(fixed_path):
                    self._log(f"Using existing rotation-fixed video: {fixed_path}\n")
                    return fixed_path
                self._log(f"Video needs re-encoding ({reason}). Fixing...\n")
                ffmpeg = _env_tool("ffmpeg")
                if not ffmpeg:
                    self._log("Warning: ffmpeg not found. Skipping rotation fix.\n")
                    return video_path
                subprocess.run(
                    [ffmpeg, "-y", "-i", video_path, "-c:v", "libx264", "-crf", "18", "-an", fixed_path],
                    capture_output=True, cwd=str(PROJ_ROOT), creationflags=subprocess.CREATE_NO_WINDOW
                )
                self._log(f"Fixed -> {fixed_path}\n\n")
                return fixed_path
        except Exception as e:
            self._log(f"Warning: Could not check rotation: {e}\n")
        return video_path

    def _detect_blender(self):
        import shutil
        import glob as glob_mod
        blender = shutil.which("blender")
        if blender:
            return blender
        patterns = [
            r"C:\Program Files\Blender Foundation\Blender *\blender.exe",
            r"C:\Program Files (x86)\Blender Foundation\Blender *\blender.exe",
        ]
        for pattern in patterns:
            matches = glob_mod.glob(pattern)
            if matches:
                return sorted(matches)[-1]
        return ""

    def _autodetect_blender(self):
        found = self._detect_blender()
        if found:
            self.retarget_blender_var.set(found)
            self._log(f"Blender found: {found}\n")
        else:
            messagebox.showwarning(
                "Blender not found",
                "Blender was not found automatically.\n\n"
                "Install Blender from blender.org or set the path manually."
            )

    # ═══════════════════════════════════════════════════════
    # ACTION HANDLERS
    # ═══════════════════════════════════════════════════════
    def _run_inference(self):
        video = self.video_path_var.get().strip()
        if not video:
            messagebox.showerror("Error", "Please select a video file.")
            return
        if not os.path.isfile(video):
            messagebox.showerror("Error", f"Video file not found:\n{video}")
            return

        video = self._fix_video_rotation(video)

        if self.hands_var.get():
            script = "tools/pipeline/pipeline_fullbody.py"
            label_suffix = " (Full Body + Hands)"
        else:
            script = "tools/pipeline/pipeline.py"
            label_suffix = ""

        args = [script, "--video", video]

        output = self.output_dir_var.get().strip()
        if output and output != "outputs/results":
            args += ["--output_root", output]

        if self.static_cam_var.get():
            args.append("-s")
        if not self.hands_var.get() and self.use_dpvo_var.get():
            args.append("--use_dpvo")
        if self.verbose_var.get():
            args.append("--verbose")
        if self.use_focal_var.get():
            args += ["--f_mm", self.focal_var.get()]

        video_stem = Path(video).stem
        output_base = output if output else "outputs/results"

        def on_done():
            out_dir = PROJ_ROOT / output_base / video_stem
            if out_dir.exists():
                self.export_dir_var.set(str(out_dir))
                self.retarget_results_var.set(str(out_dir))
                result = messagebox.askyesno(
                    "Done!",
                    f"Inference completed!\n\nOutput: {out_dir}\n\nOpen output folder?"
                )
                if result:
                    os.startfile(str(out_dir))
            else:
                messagebox.showinfo("Done", "Inference completed!")

        self._run_command(args, f"Inference{label_suffix}", on_success=on_done)

    def _run_export(self):
        results_dir = self.export_dir_var.get().strip()
        if not results_dir:
            messagebox.showerror("Error", "Please select a results directory.\n\n"
                                 "This should be the output folder from inference\n"
                                 "(e.g. outputs/results/MY_VIDEO)")
            return
        if not os.path.isdir(results_dir):
            messagebox.showerror("Error", f"Directory not found:\n{results_dir}")
            return
        if not os.path.isfile(os.path.join(results_dir, "hmr4d_results.pt")):
            messagebox.showerror("Error", f"hmr4d_results.pt not found in:\n{results_dir}\n\n"
                                 "Run inference first.")
            return

        args = ["tools/export/export_bvh.py", "--results_dir", results_dir]

        output = self.export_output_var.get().strip()
        if output:
            args += ["--output", output]

        if self.export_body_only_var.get():
            args.append("--body_only")

        fps = self.export_fps_var.get().strip()
        if fps and fps != "30":
            args += ["--fps", fps]

        scale = self.export_scale_var.get().strip()
        if scale and scale != "100":
            args += ["--scale", scale]

        self._run_command(args, "Export BVH")

    def _run_retarget(self):
        mode = self.retarget_source_var.get()
        character = self.retarget_char_var.get().strip()
        output = self.retarget_output_var.get().strip()
        blender_path = self.retarget_blender_var.get().strip()
        fps = self.retarget_fps_var.get().strip() or "30"

        if not character or not os.path.isfile(character):
            messagebox.showerror("Error", "Select a valid character file (.fbx / .dae).")
            return
        if not output:
            messagebox.showerror("Error", "Set the output path.")
            return
        if not blender_path or not os.path.isfile(blender_path):
            messagebox.showerror(
                "Blender not found",
                f"Blender not found at:\n{blender_path}\n\n"
                "Use 'Auto-detect' or set the path manually."
            )
            return

        fmt = self.retarget_format_var.get().lower()
        ext_map = {"fbx": ".fbx", "glb": ".glb", "gltf": ".gltf", "abc": ".abc", "dae": ".dae"}
        expected_ext = ext_map.get(fmt, ".fbx")
        if not output.lower().endswith(expected_ext):
            output = str(Path(output).with_suffix(expected_ext))
            self.retarget_output_var.set(output)

        script = str(PROJ_ROOT / "tools" / "retarget" / "retarget_blender.py")

        if mode == "bvh":
            bvh = self.retarget_bvh_var.get().strip()
            if not bvh or not os.path.isfile(bvh):
                messagebox.showerror("Error", "Select a valid BVH file.")
                return
            cmd = [blender_path, "--background", "--python", script, "--",
                   "--bvh", bvh, "--character", character,
                   "--output", output, "--fps", fps]
            self._run_blender_command(cmd, "Skeleton Transfer (BVH)")
            return

        results_dir = self.retarget_results_var.get().strip()
        if not results_dir or not os.path.isdir(results_dir):
            messagebox.showerror("Error", "Select a valid results folder.")
            return
        pt_file = os.path.join(results_dir, "hmr4d_results.pt")
        if not os.path.isfile(pt_file):
            messagebox.showerror("Error", f"hmr4d_results.pt not found in:\n{results_dir}\n\n"
                                          "Run Inference first.")
            return

        npz_path = os.path.join(results_dir, "motion.npz")
        prepare_script = str(PROJ_ROOT / "tools" / "retarget" / "prepare_motion.py")

        def after_prepare():
            cmd = [blender_path, "--background", "--python", script, "--",
                   "--npz", npz_path, "--character", character,
                   "--output", output, "--fps", fps]
            self._run_blender_command(cmd, "Skeleton Transfer (NPZ)")

        prep_args = [prepare_script, "--results_dir", results_dir,
                     "--out", npz_path, "--fps", fps]
        self._run_command(prep_args, "Prepare motion (.pt → .npz)", on_success=after_prepare)

    def _open_output(self):
        output = self.output_dir_var.get().strip()
        if not output:
            output = "outputs/results"
        full = PROJ_ROOT / output
        if full.exists():
            os.startfile(str(full))
        else:
            base = PROJ_ROOT / "outputs"
            if base.exists():
                os.startfile(str(base))
            else:
                messagebox.showinfo("Info", f"Output directory doesn't exist yet:\n{full}")

    def _check_gpu(self):
        self._clear_log()
        args = ["-c", (
            "import torch; "
            "print(f'PyTorch: {torch.__version__}'); "
            "print(f'CUDA Available: {torch.cuda.is_available()}'); "
            "print(f'CUDA Version: {torch.version.cuda}'); "
            "print(f'GPU: {torch.cuda.get_device_name()}'); "
            "print(f'GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB'); "
            "print(f'Compute Capability: {torch.cuda.get_device_capability()}'); "
            "import pytorch3d; print(f'PyTorch3D: OK'); "
        )]
        self._run_command(args, "GPU Info")


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════
def main():
    app = MocapOSApp()
    app.mainloop()


if __name__ == "__main__":
    main()
