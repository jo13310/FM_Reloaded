#!/usr/bin/env python3
"""
Mod file analysis and detection system for FM Reloaded.
Analyzes mod files to determine type and suggest manifest configuration.
"""

import os
import json
import re
import zipfile
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import mimetypes


class ModType:
    """Constants for mod types."""
    BEPINEX_PLUGIN = "bepinex"
    UI_BUNDLE = "ui"
    GRAPHICS = "graphics"
    TACTICS = "tactics"
    DATABASE = "database"
    SKIN = "skin"
    AUDIO = "audio"
    MISC = "misc"


class ModAnalysis:
    """Result of mod analysis."""
    
    def __init__(self):
        self.detected_type = ModType.MISC
        self.confidence = 0.0  # 0.0 to 1.0
        self.suggested_name = ""
        self.suggested_files = []
        self.detected_platforms = []
        self.warnings = []
        self.install_suggestions = []
        self.additional_info = {}


def analyze_mod_source(source_path: Path) -> ModAnalysis:
    """
    Analyze a mod source (directory or zip file) to determine its characteristics.
    
    Args:
        source_path: Path to mod directory or zip file
        
    Returns:
        ModAnalysis object with detection results
    """
    analysis = ModAnalysis()
    
    if source_path.is_file() and source_path.suffix.lower() == '.zip':
        return _analyze_zip_file(source_path)
    elif source_path.is_dir():
        return _analyze_directory(source_path)
    else:
        analysis.warnings.append("Unsupported file type. Expected directory or .zip file.")
        return analysis


def _analyze_zip_file(zip_path: Path) -> ModAnalysis:
    """Analyze a zip file without extracting it completely."""
    analysis = ModAnalysis()
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_file:
            file_list = zip_file.namelist()
            
            # Analyze file structure
            analysis = _analyze_file_list(file_list, zip_path.stem)
            
            # Check for existing manifest in zip
            manifest_found = any(
                f.lower().endswith('manifest.json') for f in file_list
            )
            if manifest_found:
                analysis.warnings.append("Zip contains manifest.json - consider using normal import instead.")
            
            # Extract some key files for deeper analysis
            temp_dir = None
            try:
                temp_dir = Path(tempfile.mkdtemp(prefix="fm_analysis_"))
                key_files = _get_key_analysis_files(file_list)
                
                for file_info in key_files:
                    try:
                        with zip_file.open(file_info) as source:
                            temp_file = temp_dir / Path(file_info).name
                            temp_file.write_bytes(source.read())
                            
                        # Analyze extracted file
                        if temp_file.suffix.lower() == '.dll':
                            _analyze_dll_file(temp_file, analysis)
                        elif temp_file.suffix.lower() in ['.json', '.txt']:
                            _analyze_text_file(temp_file, analysis)
                    except Exception:
                        continue  # Skip files that can't be extracted
                        
            finally:
                if temp_dir:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    
    except Exception as e:
        analysis.warnings.append(f"Failed to analyze zip file: {e}")
    
    return analysis


def _analyze_directory(dir_path: Path) -> ModAnalysis:
    """Analyze a directory structure."""
    analysis = ModAnalysis()
    
    try:
        # Get all files recursively
        all_files = list(dir_path.rglob("*"))
        file_list = [str(f.relative_to(dir_path)) for f in all_files if f.is_file()]
        
        analysis = _analyze_file_list(file_list, dir_path.name)
        
        # Check for existing manifest
        manifest_path = dir_path / "manifest.json"
        if manifest_path.exists():
            try:
                existing_manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                analysis.additional_info['existing_manifest'] = existing_manifest
                analysis.warnings.append("Directory already contains manifest.json - consider using normal import.")
            except Exception:
                analysis.warnings.append("Invalid manifest.json found in directory.")
        
        # Analyze key files directly
        for file_path in all_files:
            if file_path.is_file():
                if file_path.suffix.lower() == '.dll':
                    _analyze_dll_file(file_path, analysis)
                elif file_path.suffix.lower() in ['.json', '.txt', '.md']:
                    _analyze_text_file(file_path, analysis)
                    
    except Exception as e:
        analysis.warnings.append(f"Failed to analyze directory: {e}")
    
    return analysis


def _analyze_file_list(file_list: List[str], base_name: str) -> ModAnalysis:
    """Analyze file list to determine mod type."""
    analysis = ModAnalysis()
    analysis.suggested_name = _suggest_name_from_files(file_list, base_name)
    
    # Count file types
    dll_count = sum(1 for f in file_list if f.lower().endswith('.dll'))
    bundle_count = sum(1 for f in file_list if f.lower().endswith('.bundle'))
    fmf_count = sum(1 for f in file_list if f.lower().endswith('.fmf'))
    
    # Count graphics files
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tga', '.dds'}
    graphics_count = sum(1 for f in file_list 
                     if Path(f).suffix.lower() in image_extensions)
    
    # Count audio files
    audio_extensions = {'.wav', '.mp3', '.ogg', '.flac'}
    audio_count = sum(1 for f in file_list 
                    if Path(f).suffix.lower() in audio_extensions)
    
    # Analyze BepInEx patterns
    bepinex_patterns = ['bepinex/', 'plugins/', 'patchers/', 'core/']
    bepinex_score = sum(1 for pattern in bepinex_patterns 
                       if any(pattern.lower() in f.lower() for f in file_list))
    
    # Analyze UI/bundle patterns
    ui_patterns = ['ui_', 'panelids', 'graphics_', 'layouts_', 'skins_']
    ui_score = sum(1 for pattern in ui_patterns 
                   if any(pattern.lower() in f.lower() for f in file_list))
    
    # Determine mod type with confidence scoring
    if bepinex_score > 0 or dll_count > 0:
        if bepinex_score >= 2 or (dll_count > 0 and bepinex_score > 0):
            analysis.detected_type = ModType.BEPINEX_PLUGIN
            analysis.confidence = min(0.9, 0.6 + (bepinex_score * 0.1) + (dll_count * 0.1))
            analysis.suggested_files = _generate_bepinex_files(file_list)
        elif dll_count > 0:
            analysis.detected_type = ModType.BEPINEX_PLUGIN
            analysis.confidence = 0.7
            analysis.suggested_files = _generate_bepinex_files(file_list)
    
    elif bundle_count > 0:
        analysis.detected_type = ModType.UI_BUNDLE
        analysis.confidence = min(0.9, 0.5 + (bundle_count * 0.1))
        analysis.suggested_files = _generate_ui_files(file_list)
    
    elif fmf_count > 0:
        analysis.detected_type = ModType.TACTICS
        analysis.confidence = 0.8
        analysis.suggested_files = _generate_tactics_files(file_list)
    
    elif graphics_count > 5:  # Threshold for graphics mods
        analysis.detected_type = ModType.GRAPHICS
        analysis.confidence = min(0.8, 0.4 + (graphics_count * 0.02))
        graphics_subtype = _detect_graphics_subtype(file_list)
        if graphics_subtype:
            analysis.additional_info['graphics_subtype'] = graphics_subtype
        analysis.suggested_files = _generate_graphics_files(file_list, graphics_subtype)
    
    elif audio_count > 3:
        analysis.detected_type = ModType.AUDIO
        analysis.confidence = min(0.8, 0.4 + (audio_count * 0.05))
        analysis.suggested_files = _generate_audio_files(file_list)
    
    elif ui_score > 0:
        analysis.detected_type = ModType.SKIN
        analysis.confidence = min(0.7, 0.4 + (ui_score * 0.1))
        analysis.suggested_files = _generate_skin_files(file_list)
    
    # Detect target platforms
    if any('windows' in f.lower() or f.endswith('.exe') for f in file_list):
        analysis.detected_platforms.append('windows')
    if any('mac' in f.lower() or 'osx' in f.lower() for f in file_list):
        analysis.detected_platforms.append('mac')
    if any('linux' in f.lower() for f in file_list):
        analysis.detected_platforms.append('linux')
    
    # Generate installation suggestions
    analysis.install_suggestions = _generate_install_suggestions(analysis)
    
    return analysis


def _analyze_dll_file(dll_path: Path, analysis: ModAnalysis):
    """Analyze a DLL file for BepInEx compatibility."""
    try:
        # Basic file size check
        if dll_path.stat().st_size < 1024:
            analysis.warnings.append(f"DLL file {dll_path.name} is very small.")
        
        # Try to read basic info (without heavy parsing)
        with open(dll_path, 'rb') as f:
            header = f.read(1024)
            
        # Check for common BepInEx indicators
        if b'BepInEx' in header or b'Harmony' in header:
            analysis.confidence += 0.1
            
        analysis.additional_info['dll_files'] = analysis.additional_info.get('dll_files', [])
        analysis.additional_info['dll_files'].append(dll_path.name)
        
    except Exception:
        analysis.warnings.append(f"Could not analyze DLL file: {dll_path.name}")


def _analyze_text_file(file_path: Path, analysis: ModAnalysis):
    """Analyze text files for additional information."""
    try:
        content = file_path.read_text(encoding='utf-8', errors='ignore').lower()
        
        # Look for version information
        if 'version' in content and any(char.isdigit() for char in content):
            import re
            version_matches = re.findall(r'(\d+\.\d+\.\d+)', content)
            if version_matches:
                analysis.additional_info['detected_version'] = version_matches[0]
        
        # Look for author information
        author_patterns = ['author', 'created by', 'made by', 'developer']
        for pattern in author_patterns:
            if pattern in content:
                # Simple heuristic - look for nearby text
                start = content.find(pattern)
                if start >= 0:
                    snippet = content[start:start+100]
                    words = snippet.split()
                    for word in words:
                        if word.replace(',', '').replace(':', '').strip().title() and len(word.replace(',', '').replace(':', '').strip()) > 2:
                            if 'author' not in analysis.additional_info:
                                analysis.additional_info['author'] = word.replace(',', '').replace(':', '').strip().title()
                                break
        
        # Look for description
        if file_path.name.lower() in ['readme.txt', 'readme.md', 'description.txt']:
            lines = content.split('\n')[:5]  # First 5 lines
            clean_lines = [line.strip() for line in lines if line.strip() and len(line.strip()) > 10]
            if clean_lines and 'description' not in analysis.additional_info:
                analysis.additional_info['description'] = ' '.join(clean_lines[:2])  # First 2 meaningful lines
        
    except Exception:
        pass  # Skip files that can't be read


def _get_key_analysis_files(file_list: List[str]) -> List[str]:
    """Get key files that should be extracted for analysis."""
    key_files = []
    max_files = 10  # Limit to avoid extracting too much
    
    for file_path in file_list[:50]:  # Check first 50 files
        file_lower = file_path.lower()
        if (file_lower.endswith('.dll') or 
            file_lower.endswith('.json') or
            any(keyword in file_lower for keyword in ['readme', 'install', 'info'])):
            key_files.append(file_path)
            if len(key_files) >= max_files:
                break
    
    return key_files


def _suggest_name_from_files(file_list: List[str], base_name: str) -> str:
    """Suggest a mod name based on file contents."""
    # Remove common prefixes/suffixes from base name
    clean_name = base_name
    prefixes = ['fm26_', 'fm_', 'mod_', 'v']
    suffixes = ['_master', '_main', '_release', '_final']
    
    for prefix in prefixes:
        if clean_name.lower().startswith(prefix):
            clean_name = clean_name[len(prefix):]
    
    for suffix in suffixes:
        if clean_name.lower().endswith(suffix):
            clean_name = clean_name[:-len(suffix)]
    
    # If we still don't have a good name, try to find it in files
    if len(clean_name) < 3:
        for file_path in file_list[:10]:
            file_name = Path(file_path).stem
            if len(file_name) > 3 and not file_name.lower().startswith('readme'):
                clean_name = file_name
                break
    
    return clean_name.strip('_- ')


def _detect_graphics_subtype(file_list: List[str]) -> Optional[str]:
    """Detect the subtype of graphics mod."""
    file_list_lower = [f.lower() for f in file_list]
    
    # Check for kits
    if any('kit' in f for f in file_list_lower):
        return "kits"
    
    # Check for faces/portraits
    if any(keyword in f for f in file_list_lower 
           for keyword in ['face', 'portrait', 'player']):
        return "faces"
    
    # Check for logos/badges
    if any(keyword in f for f in file_list_lower 
           for keyword in ['logo', 'badge', 'icon']):
        return "logos"
    
    return None


def _generate_bepinex_files(file_list: List[str]) -> List[Dict]:
    """Generate file entries for BepInEx plugins."""
    files = []
    
    for file_path in file_list:
        if file_path.lower().endswith('.dll'):
            # Determine if it's a plugin or core component
            if 'core' in file_path.lower() or 'bepinex' in file_path.lower():
                target = f"BepInEx/core/{Path(file_path).name}"
            else:
                target = f"BepInEx/plugins/{Path(file_path).name}"
            
            files.append({
                "source": file_path,
                "target_subpath": target
            })
    
    return files


def _generate_ui_files(file_list: List[str]) -> List[Dict]:
    """Generate file entries for UI/bundle mods."""
    files = []
    
    for file_path in file_list:
        if file_path.lower().endswith('.bundle'):
            files.append({
                "source": file_path,
                "target_subpath": Path(file_path).name
            })
    
    return files


def _generate_tactics_files(file_list: List[str]) -> List[Dict]:
    """Generate file entries for tactics mods."""
    files = []
    
    for file_path in file_list:
        if file_path.lower().endswith('.fmf'):
            files.append({
                "source": file_path,
                "target_subpath": f"tactics/{Path(file_path).name}"
            })
    
    return files


def _generate_graphics_files(file_list: List[str], subtype: Optional[str]) -> List[Dict]:
    """Generate file entries for graphics mods."""
    files = []
    
    # Determine target directory
    if subtype == "kits":
        base_target = "graphics/kits"
    elif subtype == "faces":
        base_target = "graphics/faces"
    elif subtype == "logos":
        base_target = "graphics/logos"
    else:
        base_target = "graphics"
    
    # Add image files
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tga', '.dds'}
    
    for file_path in file_list:
        if Path(file_path).suffix.lower() in image_extensions:
            # Preserve directory structure
            rel_path = Path(file_path)
            if rel_path.parent.name:
                target = f"{base_target}/{rel_path.parent.name}/{rel_path.name}"
            else:
                target = f"{base_target}/{rel_path.name}"
            
            files.append({
                "source": file_path,
                "target_subpath": target
            })
    
    return files


def _generate_audio_files(file_list: List[str]) -> List[Dict]:
    """Generate file entries for audio mods."""
    files = []
    audio_extensions = {'.wav', '.mp3', '.ogg', '.flac'}
    
    for file_path in file_list:
        if Path(file_path).suffix.lower() in audio_extensions:
            files.append({
                "source": file_path,
                "target_subpath": f"audio/{Path(file_path).name}"
            })
    
    return files


def _generate_skin_files(file_list: List[str]) -> List[Dict]:
    """Generate file entries for skin mods."""
    files = []
    
    for file_path in file_list:
        if (file_path.lower().endswith('.bundle') or 
            'skin' in file_path.lower() or
            'ui_' in file_path.lower()):
            files.append({
                "source": file_path,
                "target_subpath": f"skins/{Path(file_path).name}"
            })
    
    return files


def _generate_install_suggestions(analysis: ModAnalysis) -> List[str]:
    """Generate installation suggestions based on analysis."""
    suggestions = []
    
    if analysis.detected_type == ModType.BEPINEX_PLUGIN:
        suggestions.append("This appears to be a BepInEx plugin.")
        suggestions.append("It will be installed to BepInEx/plugins or BepInEx/core.")
        
    elif analysis.detected_type == ModType.UI_BUNDLE:
        suggestions.append("This appears to be a UI/bundle mod.")
        suggestions.append("Bundle files will be installed to the FM26 data directory.")
        
    elif analysis.detected_type == ModType.GRAPHICS:
        subtype = analysis.additional_info.get('graphics_subtype', 'general')
        suggestions.append(f"This appears to be a graphics mod ({subtype} type).")
        suggestions.append("Files will be installed to Documents/FM26/graphics/")
        
    elif analysis.detected_type == ModType.TACTICS:
        suggestions.append("This appears to be a tactics mod.")
        suggestions.append(".fmf files will be installed to Documents/FM26/tactics/")
        
    elif analysis.detected_type == ModType.AUDIO:
        suggestions.append("This appears to be an audio mod.")
        suggestions.append("Audio files will be installed to Documents/FM26/audio/")
    
    if analysis.confidence < 0.6:
        suggestions.append("Detection confidence is low. Please review the suggested manifest.")
    
    if analysis.detected_platforms:
        platforms = ", ".join(analysis.detected_platforms)
        suggestions.append(f"Detected platforms: {platforms}")
    
    return suggestions


def generate_basic_manifest(analysis: ModAnalysis, user_name: str = "", 
                        user_description: str = "") -> Dict:
    """
    Generate a basic manifest from analysis results.
    
    Args:
        analysis: ModAnalysis results
        user_name: Optional user-provided name
        user_description: Optional user-provided description
        
    Returns:
        Basic manifest dictionary
    """
    manifest = {
        "name": user_name or analysis.suggested_name or "Unknown Mod",
        "version": analysis.additional_info.get('detected_version', '1.0.0'),
        "type": _map_type_to_manifest_type(analysis.detected_type),
        "author": analysis.additional_info.get('author', 'Unknown'),
        "description": user_description or analysis.additional_info.get('description', 
                                                      f"Auto-generated manifest for {analysis.detected_type} mod"),
        "files": analysis.suggested_files
    }
    
    # Add compatibility info if detected
    if analysis.detected_platforms:
        manifest["compatibility"] = {
            platform: True for platform in analysis.detected_platforms
        }
    
    # Add graphics subtype if detected
    if analysis.additional_info.get('graphics_subtype'):
        manifest["graphics_subtype"] = analysis.additional_info['graphics_subtype']
    
    return manifest


def _map_type_to_manifest_type(detected_type: str) -> str:
    """Map internal detection type to manifest type."""
    mapping = {
        ModType.BEPINEX_PLUGIN: "misc",  # BepInEx plugins go to misc
        ModType.UI_BUNDLE: "ui",
        ModType.GRAPHICS: "graphics",
        ModType.TACTICS: "tactics",
        ModType.DATABASE: "database",
        ModType.SKIN: "skins",
        ModType.AUDIO: "audio",
        ModType.MISC: "misc"
    }
    return mapping.get(detected_type, "misc")
