"""Unit tests for main build orchestrator (build.py)."""

import pytest
from pathlib import Path
import sys
import tempfile
from datetime import datetime

# Add scripts/build to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "build"))

# Import functions from build.py
import build
from build_state import BuildState, StepStatus


class TestParseArgs:
    """Tests for parse_args function."""
    
    def test_parse_args_defaults(self, monkeypatch):
        """Test default argument values."""
        monkeypatch.setattr(sys, 'argv', ['build.py'])
        args = build.parse_args()
        
        assert args.resume is True
        assert args.clean is False
        assert args.from_step is None
        assert args.skip_steps == []
        assert args.force is False
        assert args.no_parallel is False
        assert args.max_parallel == 2
    
    def test_parse_args_clean_flag(self, monkeypatch):
        """Test --clean flag."""
        monkeypatch.setattr(sys, 'argv', ['build.py', '--clean'])
        args = build.parse_args()
        
        assert args.clean is True
    
    def test_parse_args_from_step(self, monkeypatch):
        """Test --from-step flag."""
        monkeypatch.setattr(sys, 'argv', ['build.py', '--from-step', 'validate_versions'])
        args = build.parse_args()
        
        assert args.from_step == 'validate_versions'
    
    def test_parse_args_skip_step_single(self, monkeypatch):
        """Test --skip-step flag with single step."""
        monkeypatch.setattr(sys, 'argv', ['build.py', '--skip-step', 'sign_package'])
        args = build.parse_args()
        
        assert args.skip_steps == ['sign_package']
    
    def test_parse_args_skip_step_multiple(self, monkeypatch):
        """Test --skip-step flag with multiple steps."""
        monkeypatch.setattr(sys, 'argv', [
            'build.py',
            '--skip-step', 'sign_package',
            '--skip-step', 'inspect_package'
        ])
        args = build.parse_args()
        
        assert args.skip_steps == ['sign_package', 'inspect_package']
    
    def test_parse_args_force_flag(self, monkeypatch):
        """Test --force flag."""
        monkeypatch.setattr(sys, 'argv', ['build.py', '--force'])
        args = build.parse_args()
        
        assert args.force is True
    
    def test_parse_args_no_parallel(self, monkeypatch):
        """Test --no-parallel flag."""
        monkeypatch.setattr(sys, 'argv', ['build.py', '--no-parallel'])
        args = build.parse_args()
        
        assert args.no_parallel is True
    
    def test_parse_args_max_parallel(self, monkeypatch):
        """Test --max-parallel flag."""
        monkeypatch.setattr(sys, 'argv', ['build.py', '--max-parallel', '4'])
        args = build.parse_args()
        
        assert args.max_parallel == 4
    
    def test_parse_args_non_interactive(self, monkeypatch):
        """Test --non-interactive flag."""
        monkeypatch.setattr(sys, 'argv', ['build.py', '--non-interactive'])
        args = build.parse_args()
        
        assert args.non_interactive is True


class TestLoadState:
    """Tests for load_state function."""
    
    def test_load_state_nonexistent_file(self, tmp_path):
        """Test loading state when file doesn't exist."""
        state_file = tmp_path / ".build-state.json"
        
        state = build.load_state(state_file)
        
        assert state is None
    
    def test_load_state_existing_file(self, tmp_path):
        """Test loading state from existing file."""
        state_file = tmp_path / ".build-state.json"
        
        # Create a state and save it
        original_state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        original_state.mark_step_started("step_1")
        original_state.mark_step_completed("step_1", 1.5)
        original_state.save_to_file(state_file)
        
        # Load it back
        loaded_state = build.load_state(state_file)
        
        assert loaded_state is not None
        assert loaded_state.build_id == "test-build"
        assert loaded_state.is_step_complete("step_1")
    
    def test_load_state_corrupted_file(self, tmp_path, capsys):
        """Test loading corrupted state file."""
        state_file = tmp_path / ".build-state.json"
        state_file.write_text("invalid json {{{")
        
        state = build.load_state(state_file)
        
        # Should return None and print warning
        assert state is None
        captured = capsys.readouterr()
        assert "WARN" in captured.out or "warn" in captured.out.lower()


class TestSaveState:
    """Tests for save_state function."""
    
    def test_save_state_creates_file(self, tmp_path):
        """Test that save_state creates the state file."""
        state_file = tmp_path / ".build-state.json"
        
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        
        build.save_state(state, state_file)
        
        assert state_file.exists()
    
    def test_save_state_preserves_data(self, tmp_path):
        """Test that save_state preserves all data."""
        state_file = tmp_path / ".build-state.json"
        
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        state.mark_step_started("step_1")
        state.mark_step_completed("step_1", 2.5)
        
        build.save_state(state, state_file)
        
        # Load it back
        loaded_state = BuildState.load_from_file(state_file)
        assert loaded_state.build_id == "test-build"
        assert loaded_state.is_step_complete("step_1")
        assert loaded_state.steps["step_1"].duration_seconds == 2.5


class TestDisplaySummary:
    """Tests for display_summary function."""
    
    def test_display_summary_success(self, capsys):
        """Test summary display for successful build."""
        from rich.console import Console
        
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        state.mark_step_started("step_1")
        state.mark_step_completed("step_1", 1.0)
        state.mark_step_started("step_2")
        state.mark_step_completed("step_2", 2.0)
        
        console = Console()
        build.display_summary(state, console, success=True)
        
        captured = capsys.readouterr()
        assert "SUCCESS" in captured.out or "success" in captured.out.lower()
    
    def test_display_summary_failure(self, capsys):
        """Test summary display for failed build."""
        from rich.console import Console
        
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        state.mark_step_started("step_1")
        state.mark_step_completed("step_1", 1.0)
        state.mark_step_started("step_2")
        state.mark_step_failed("step_2", "Test error")
        
        console = Console()
        build.display_summary(state, console, success=False)
        
        captured = capsys.readouterr()
        assert "FAILED" in captured.out or "failed" in captured.out.lower()
    
    def test_display_summary_includes_statistics(self, capsys):
        """Test that summary includes step statistics."""
        from rich.console import Console
        
        state = BuildState(
            build_id="test-build",
            start_time=datetime.now(),
            last_update=datetime.now(),
            steps={}
        )
        state.mark_step_started("step_1")
        state.mark_step_completed("step_1", 1.0)
        state.mark_step_started("step_2")
        state.mark_step_failed("step_2", "Test error")
        state.mark_step_skipped("step_3")
        
        console = Console()
        build.display_summary(state, console, success=False)
        
        captured = capsys.readouterr()
        # Should show counts
        assert "1" in captured.out  # 1 completed
        assert "1" in captured.out  # 1 failed
        assert "1" in captured.out  # 1 skipped


class TestSetupLogging:
    """Tests for setup_logging function."""
    
    def test_setup_logging_creates_logger(self, tmp_path):
        """Test that setup_logging creates a logger."""
        log_file = tmp_path / "test.log"
        
        logger = build.setup_logging(log_file)
        
        assert logger is not None
        assert logger.name == "build"
    
    def test_setup_logging_creates_log_file(self, tmp_path):
        """Test that setup_logging creates the log file."""
        log_file = tmp_path / "test.log"
        
        logger = build.setup_logging(log_file)
        logger.info("Test message")
        
        assert log_file.exists()
        content = log_file.read_text()
        assert "Test message" in content
