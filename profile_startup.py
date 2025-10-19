#!/usr/bin/env python3
"""Profile ADH CLI startup time."""

import cProfile
import pstats
import io
import time


def profile_imports():
    """Profile the import phase."""
    start = time.time()

    # Import the main app
    from adh_cli.app import ADHApp

    import_time = time.time() - start
    print(f"\n{'=' * 70}")
    print(f"Import time: {import_time:.3f}s")
    print(f"{'=' * 70}\n")

    return ADHApp


def profile_initialization():
    """Profile app initialization."""
    from adh_cli.app import ADHApp

    start = time.time()
    app = ADHApp()
    init_time = time.time() - start

    print(f"\n{'=' * 70}")
    print(f"Initialization time: {init_time:.3f}s")
    print(f"{'=' * 70}\n")

    return app


def main():
    """Run profiling."""
    print("Profiling ADH CLI startup...")
    print("=" * 70)

    # Profile import phase
    print("\n1. Profiling imports...")
    pr = cProfile.Profile()
    pr.enable()
    profile_imports()  # We don't need the return value
    pr.disable()

    # Print import statistics
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(30)  # Top 30 slowest functions
    print(s.getvalue())

    # Profile initialization phase
    print("\n2. Profiling initialization...")
    pr2 = cProfile.Profile()
    pr2.enable()
    profile_initialization()  # We don't need the return value
    pr2.disable()

    # Print initialization statistics
    s2 = io.StringIO()
    ps2 = pstats.Stats(pr2, stream=s2).sort_stats("cumulative")
    ps2.print_stats(30)  # Top 30 slowest functions
    print(s2.getvalue())

    print("\n" + "=" * 70)
    print("Profiling complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
