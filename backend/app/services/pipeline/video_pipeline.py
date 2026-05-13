import os
import json
import asyncio
from typing import List, Dict, Any
from pathlib import Path

from app.core.logging import setup_logging
from app.services.ai import get_llm
from app.services.filesystem.path_handler import PathHandler
from app.services.library.video_service import VideoService
from app.services.processing.semantic_processing import semantic_split
from app.services.processing.video_processing import map_segment_to_subtitles, extract_video_clip
from app.utils.srt import parse_srt
from app.utils.text import load_text

logger = setup_logging(__name__)

async def process_video_scenes(series: str, season: str, episode: str, base_dir: str = "data") -> Dict[str, Any]:
    """
    Process an episode to extract video scenes based on semantic segments.
    """
    path_handler = PathHandler(series, season, episode, base_dir=base_dir)
    video_service = VideoService(base_dir=base_dir)
    
    # 1. Validation
    srt_path = Path(path_handler.get_srt_file_path())
    plot_path = Path(path_handler.get_raw_plot_file_path())
    video_path = video_service.find_video_for_episode(series, season, episode)
    
    if not srt_path.exists():
        return {"status": "error", "message": f"SRT file missing: {srt_path}"}
    if not plot_path.exists():
        return {"status": "error", "message": f"Plot file missing: {plot_path}"}
    if not video_path:
        return {"status": "error", "message": f"Video file missing for {series} {season} {episode}"}

    logger.info(f"Starting video scene analysis for {series} {season} {episode}")
    
    try:
        llm = get_llm()
        
        # 2. Get Semantic Segments
        semantic_segments_path = path_handler.get_semantic_segments_path()
        if os.path.exists(semantic_segments_path):
            logger.info(f"Loading existing semantic segments from: {semantic_segments_path}")
            with open(semantic_segments_path, "r", encoding="utf-8") as f:
                semantic_segments = json.load(f)
        else:
            logger.info("Generating new semantic segments.")
            # Use entity normalized plot if available, else raw
            norm_plot_path = path_handler.get_entity_normalized_plot_file_path()
            if os.path.exists(norm_plot_path):
                plot_text = load_text(norm_plot_path)
            else:
                plot_text = load_text(str(plot_path))
            
            semantic_segments = await semantic_split(text=plot_text, llm=llm)
            with open(semantic_segments_path, "w", encoding="utf-8") as f:
                json.dump(semantic_segments, f, indent=2, ensure_ascii=False)
        
        # 3. Load Subtitles
        with open(srt_path, "r", encoding="utf-8") as f:
            srt_content = f.read()
        srt_entries = parse_srt(srt_content)
        
        # 4. Process each segment
        scenes_dir = path_handler.get_episode_scenes_dir()
        
        # Clear existing clips folder if it exists
        if os.path.exists(scenes_dir):
            logger.info(f"Clearing existing clips folder: {scenes_dir}")
            import shutil
            shutil.rmtree(scenes_dir)
        
        os.makedirs(scenes_dir, exist_ok=True)
        
        extracted_clips = []
        
        for i, segment in enumerate(semantic_segments):
            logger.info(f"Processing scene {i+1}/{len(semantic_segments)}")
            
            # Find matching subtitles
            mapping = await map_segment_to_subtitles(segment, srt_entries, llm)
            if not mapping:
                logger.warning(f"Could not map scene {i+1} to subtitles")
                continue
                
            start_idx = mapping.get("start_index")
            end_idx = mapping.get("end_index")
            
            # Find entries by index
            start_entry = next((e for e in srt_entries if e.index == start_idx), None)
            end_entry = next((e for e in srt_entries if e.index == end_idx), None)
            
            if not start_entry or not end_entry:
                logger.warning(f"Could not find subtitle entries for indices {start_idx}-{end_idx}")
                continue
                
            # 5. Extract Clip
            output_path = path_handler.get_scene_clip_path(i + 1)
            success = extract_video_clip(
                str(video_path),
                output_path,
                start_entry.start_time,
                end_entry.end_time
            )
            
            if success:
                extracted_clips.append({
                    "scene_index": i + 1,
                    "file_path": output_path,
                    "start_time": start_entry.start_time,
                    "end_time": end_entry.end_time,
                    "segment_text": segment
                })
        
        # Save scene metadata
        metadata_path = os.path.join(scenes_dir, "scenes_metadata.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(extracted_clips, f, indent=2, ensure_ascii=False)
            
        # Update DB status
        try:
            from app.repositories import DatabaseSessionManager
            from app.models.narrative import EpisodeMetadata, SeasonMetadata
            from sqlmodel import select
            
            db_manager = DatabaseSessionManager()
            with db_manager.session_scope() as session:
                # Find the episode in the DB
                stmt = (
                    select(EpisodeMetadata)
                    .join(SeasonMetadata)
                    .where(SeasonMetadata.series_code == series.upper())
                    .where(SeasonMetadata.season_code == season.upper())
                    .where(EpisodeMetadata.episode_code == episode.upper())
                )
                db_episode = session.exec(stmt).first()
                if db_episode:
                    db_episode.clips_completed = True
                    session.add(db_episode)
                    session.commit()
                    logger.info(f"Updated clips_completed=True in DB for {series} {season} {episode}")
        except Exception as e:
            logger.warning(f"Could not update clips_completed in DB: {e}")

        return {
            "status": "success",
            "message": f"Successfully extracted {len(extracted_clips)} scenes",
            "scenes": extracted_clips
        }
        
    except Exception as e:
        logger.error(f"Error in video scene pipeline: {e}")
        return {"status": "error", "message": str(e)}
