import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

def test_imports():
    print("Testing imports from app.api.v1.library context...")
    
    # Verify we can import the refactored class name correctly from pipeline
    from app.services.analysis.pipeline import NarrativeArcExtractionPipelineService
    print("Successfully imported NarrativeArcExtractionPipelineService!")
    
    # Initialize it
    pipeline = NarrativeArcExtractionPipelineService()
    print("Successfully instantiated NarrativeArcExtractionPipelineService!")

if __name__ == "__main__":
    test_imports()
