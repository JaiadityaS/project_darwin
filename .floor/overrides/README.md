# .floor/overrides

Build overrides that the repair agent may change (PRD F4.2). No file here has a code owner.

Each file holds the CMake flags for one published artifact. The build reads the file if it exists. The gate verifies every change before a merge.
