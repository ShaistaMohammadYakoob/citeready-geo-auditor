"""Shared, motion-safe keyframes for CiteReady's dashboard presentation."""

from __future__ import annotations


def animation_css() -> str:
    """Return the dashboard's restrained CSS animations."""

    return """
    @keyframes cr-nav-enter {
      from { opacity: 0; transform: translateY(-8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes cr-fade-up {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }
    @keyframes cr-slide-in {
      from { opacity: 0; transform: translateX(-10px); }
      to { opacity: 1; transform: translateX(0); }
    }
    @keyframes cr-mesh-shift {
      0%, 100% { background-position: 0% 50%; }
      50% { background-position: 100% 50%; }
    }
    @keyframes cr-progress-fill {
      from { transform: scaleX(0); }
      to { transform: scaleX(1); }
    }
    @keyframes cr-score-reveal {
      from { opacity: 0; transform: translateY(10px) scale(.96); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes cr-active-pulse {
      0%, 100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, .38); }
      50% { box-shadow: 0 0 0 6px rgba(56, 189, 248, 0); }
    }
    @keyframes cr-light-sweep {
      from { transform: translateX(-130%); }
      to { transform: translateX(160%); }
    }
    @keyframes cr-ripple {
      from { opacity: .8; transform: scale(.65); }
      to { opacity: 0; transform: scale(1.15); }
    }
    """
