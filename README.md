import pypandoc

readme = r'''# Screw Contact Generator (ANSYS Mechanical ACT)

**Version:** 1.3  
**Target environment:** ANSYS Mechanical 2019 R2  
**Scripting engine:** ACT Console / IronPython 2.7

Automatically creates **Bonded MPC contact regions** between nodes of beam-type screw line bodies and circular hole edges in surrounding solid bodies. It supports both full circular edges and circular holes represented by multiple arc segments.

Version 1.3 also adds faster geometry processing, optimized existing-contact scans, execution timing, and safer default settings.

---

## Overview

The script identifies screw line bodies from the Mechanical geometry, groups connected line bodies into individual screws, identifies the screw nodes, and searches for suitable circular edges on nearby solid bodies.

For each detected match, it creates a contact region with:

- **Contact type:** Bonded
- **Contact formulation:** MPC
- **Contact/source scope:** screw node vertex (or coincident vertices representing that node)
- **Target scope:** circular hole edge; for a segmented hole, all arc segments in the detected circle
- **Pinball region:** Radius
- **Pinball radius:** detected edge radius + `PINBALL_ADD_MM` (default: 0.3 mm)

The script creates or reuses a connection group named `screwContacts` by default.

> **Important:** Always start with `DRY_RUN = True`. Review the console report and verify the detected screw numbering, edge matches, and unmatched nodes before allowing model changes.

---

## Main features

- Automatically detects beam-screw line bodies and groups connected segments into screws using shared node positions.
- Numbers screws in geometry-tree order by default.
- Identifies top, middle, and bottom screw nodes.
- Detects full circular edges and reconstructs circles from segmented arc edges.
- Groups arcs by fitted circle center, radius, and plane orientation.
- Uses a fast closed-form arc geometry calculation by default, with an initial cross-check against the points-based method and automatic fallback when a mismatch is detected.
- Selects the smallest concentric circular edge per nearby solid body as the hole edge for middle and bottom nodes.
- Detects larger concentric edges at the top end for top-edge matching.
- Supports per-screw overrides for top-end selection and top-edge selection.
- Supports pilot runs on selected screw numbers.
- Preserves existing contacts on reruns and creates only missing contacts.
- Can recognize existing contacts by planned name and/or geometry scope.
- Can optionally identify and delete conflicting contacts, but this is disabled by default.
- Can optionally rename screw line bodies in the geometry tree.
- Uses spatial prefiltering to reduce the number of circular edges processed.
- Uses Mechanical transactions in batches when the API provides transaction support.
- Reports matching results, rejected or unused arc groups, unmatched nodes, contact creation failures, and timing by phase.

---

## Requirements and compatibility

- ANSYS Mechanical **2019 R2**.
- IronPython **2.7** environment provided by Mechanical.
- A Mechanical model containing:
  - screw representations as wire/line bodies with vertices at the relevant contact locations;
  - surrounding solid bodies containing circular hole edges.
- The script must be run from within Mechanical, where `ExtAPI`, `GeoData`, `Quantity`, and the Mechanical API objects are available.

The script is written for the Mechanical 2019 R2 API. Compatibility with other ANSYS releases has not been established by this repository description and should be tested before use.

---

## Installation and execution

1. Open the project in ANSYS Mechanical.
2. Make sure the screw geometry is represented by line/wire bodies and that the hole boundaries are circular edges on the surrounding solid bodies.
3. Open the ACT Console or create a Mechanical Python Code/Script snippet suitable for your workflow.
4. Open `screwContactCreatorScript - v1.3.py`.
5. Review the **USER SETTINGS** section at the top of the script.
6. Keep `DRY_RUN = True` for the first run.
7. Execute the script in Mechanical.
8. Review the console output:
   - number of wire and solid bodies found;
   - detected screws and their numbering;
   - full and segmented circular edges detected;
   - proposed top, middle, and bottom matches;
   - existing contacts and planned new contacts;
   - unmatched nodes and any warnings.
9. If the results are correct, set `DRY_RUN = False` and run the script again.
10. Inspect the generated connection group and contact scopes in Mechanical before solving.

The script does not provide a standalone Python command-line interface. It must run inside Mechanical.

---

## Configuration

All user-adjustable settings are located near the beginning of the script under `USER SETTINGS`. Change the values directly in the script before execution.

### General matching settings

| Setting | Default | Description |
|---|---:|---|
| `DRY_RUN` | `True` | When `True`, reports planned changes without modifying the model. Set to `False` to rename bodies and create contacts. |
| `PILOT_SCREWS` | `None` | `None` processes all screws. A list such as `[1, 3]` restricts processing to those screw numbers. |
| `PINBALL_ADD_MM` | `0.3` | Added to the detected circular edge radius to define the pinball radius. |
| `END_TOL_MM` | `3.0` | Maximum node-to-edge-center distance for top and bottom matching. |
| `MID_TOL_MM` | `2.0` | Maximum node-to-edge-center distance for middle-node matching. |
| `MAX_EDGES_MID` | `2` | Maximum number of hole edges assigned to each middle node, normally one per different body. |
| `MID_LIMIT_OVERRIDE` | `{}` | Per-screw/per-middle-node override. Example: `{(1, "MID2"): 1}`. |
| `MIN_RADIUS_MM` | `0.5` | Circular edges with a smaller radius are ignored. |
| `LENGTH_FACTOR_TO_MM` | `None` | `None` attempts to infer the geometry unit from `GeoData.Unit`. Set explicitly if the API unit conversion is not correct. |

### Existing contacts and reruns

| Setting | Default | Description |
|---|---:|---|
| `GROUP_NAME` | `"screwContacts"` | Exact name of the connection group used by the script. |
| `REBUILD_FROM_SCRATCH` | `False` | If `True`, deletes the entire named group, including its folders and contacts, before rebuilding. |
| `CHECK_EXISTING_BY_SCOPE` | `True` | Recognizes existing contacts by name or matching geometry scope. If `False`, recognition is name-based only. |
| `FAST_EXISTING_SCAN` | `True` | Accepts a contact whose name matches a planned name without reading its scope. This speeds up large existing groups. |
| `DELETE_CONFLICTING_CONTACTS` | `False` | If enabled, deletes existing contacts that use a node belonging to this script but target an edge not selected by the current matching. Review the conflict report before enabling. |
| `LIST_NEW_CONTACTS` | `True` | Lists the names of newly created contacts. |
| `LIST_NEW_MAX` | `100` | Maximum number of new contact names printed. |

**Rerun behavior:** With the default settings, the script keeps the existing connection group and its contacts, recognizes contacts that are already present, and creates only missing contacts. Existing contacts recognized by name or scope are not recreated.

If the script cannot safely read existing contacts or their scopes, it may skip creation to avoid producing duplicates. The console report explains the reason. Do not disable scope checking unless name-only recognition is acceptable for your model.

`REBUILD_FROM_SCRATCH = True` is destructive: it removes the whole configured group, including any folders or manually maintained contacts inside it.

### Top node and top edge

| Setting | Default | Description |
|---|---:|---|
| `TOP_END` | `"auto"` | `"auto"` detects the top end; `"first"` or `"last"` forces the corresponding end in the screw's axis ordering. |
| `TOP_END_OVERRIDE` | `{}` | Per-screw top-end override. Example: `{7: "last"}`. |
| `TOP_COLLISION_RULE` | `"larger_edge"` | If both ends qualify as top candidates: `"larger_edge"`, `"first"`, or `"last"`. |
| `TOP_RULE` | `"closest_above_hole"` | Selects the top extra concentric edge. `"largest"` selects the largest eligible edge. |
| `TOP_RADIUS_OVERRIDE` | `{}` | Selects a top edge by radius for a particular screw. Example: `{7: 3.5}`. |
| `TOP_EDGE_OVERRIDE` | `{}` | Selects a top edge by edge ID for a particular screw. Example: `{7: 5678}`. The ID may identify any segment of the selected edge. |
| `TOP_MAX_RADIUS_MM` | `60.0` | Larger top circular edges are ignored. |
| `CONCENTRIC_TOL_MM` | `0.05` | Maximum center separation for edges to be treated as concentric. |
| `RADIUS_STEP_MIN_MM` | `0.05` | Minimum amount by which a candidate top edge must exceed the hole-edge radius. |

In automatic mode, the script checks both ends of each screw for larger concentric circular edges. If both ends qualify, it applies `TOP_COLLISION_RULE` and prints a warning so the selected end can be checked. Use `TOP_END_OVERRIDE` when the automatic decision is not appropriate.

For the top edge, the script considers eligible larger concentric edges on the selected top end. `TOP_EDGE_OVERRIDE` takes precedence over `TOP_RADIUS_OVERRIDE`; if an override does not identify an eligible candidate, the script reports the issue and falls back to the configured selection rule.

### Segmented circular holes

| Setting | Default | Description |
|---|---:|---|
| `INCLUDE_SEGMENTED_HOLES` | `True` | Combines arc segments belonging to the same circle into one target. If `False`, only full single-edge circles are used. |
| `CIRCLE_MATCH_TOL_MM` | `0.05` | Tolerance for matching fitted arc centers and radii. |
| `MIN_ARCS_IN_CIRCLE` | `2` | Minimum number of arcs required to form a segmented circular edge. |
| `MIN_CIRCLE_COVERAGE` | `0.0` | Minimum fraction of a full circle covered by the grouped arcs. `0.0` disables this coverage threshold; `0.5` requires at least 50%. |
| `ARC_FIT_TOL_FRAC` | `0.02` | Points-method fit tolerance as a fraction of the fitted radius. |
| `LIST_ARC_GROUPS_MAX` | `30` | Maximum number of accepted segmented arc groups listed in the report. |

A segmented circular target is represented by the IDs of all arc edges grouped into that circle. The contact target scope therefore includes all segments in the group, not just one arc.

Arc groups are formed within each solid body. The script checks fitted center, radius, and plane orientation. Groups that do not meet the configured minimum arc count or coverage are not accepted as segmented hole edges.

### Screw numbering and naming

| Setting | Default | Description |
|---|---:|---|
| `SCREW_ORDER` | `"tree"` | `"tree"` numbers screws in geometry-tree order; `"position"` numbers by the screw's position. |
| `RENAME_SCREWS_IN_TREE` | `True` | Renames screw line bodies in the geometry tree using the generated screw names. |
| `SCREW_PREFIX` | `"Screw-"` | Prefix used for screw names. |
| `SCREW_SEGMENT_SUFFIX` | `False` | If `True`, multiple line bodies belonging to one screw receive suffixes such as `-Seg1`. |
| `NAME_SEPARATOR` | `" - "` | Separator between screw and edge portions of contact names. |
| `INCLUDE_TREE_NAME_IN_CONTACT` | `False` | Optionally adds a tag based on the original geometry-tree name to contact names. This is automatically disabled when `RENAME_SCREWS_IN_TREE` is `True`. |
| `EXTRACT_FROM_PARENTHESES` | `False` | When tree-name tagging is active, uses text inside parentheses as the tag. |

Typical generated names:

- Screw body: `Screw-0001`
- Contact: `Screw-0001 - TopEdge-6016`

The screw number is based on the selected `SCREW_ORDER`. With the default `"tree"` setting, the numbering follows geometry-tree order.

### Performance and reporting

| Setting | Default | Description |
|---|---:|---|
| `PREFILTER_EDGES` | `True` | Drops circular edges whose centers are not near any screw node before more detailed processing. |
| `PREFILTER_MARGIN_MM` | `0.5` | Extra distance used by the edge prefilter. |
| `ARC_METHOD` | `"closed_form"` | `"closed_form"` uses the fast chord/arc-length/centroid calculation; `"points"` uses edge points. |
| `ARC_CROSSCHECK_N` | `3` | Number of initial arcs cross-checked against the points method. A detected mismatch switches the calculation to the points method. |
| `FAST_PROPERTY_ORDER` | `True` | Assigns scopes last to reduce Mechanical tree updates. |
| `USE_TRANSACTION` | `True` | Uses Mechanical transactions if the current environment exposes the `Transaction` API. |
| `TX_BATCH_SCREWS` | `20` | Number of screws processed per transaction batch. |
| `SHOW_TIMING` | `True` | Shows elapsed time and estimated remaining time in progress output. |
| `SHOW_PHASE_TIMES` | `True` | Prints elapsed time for each processing phase in the final report. |
| `VERBOSE_MATCHES` | `False` | Prints every individual node-to-edge match. |
| `PROGRESS_EVERY` | `25` | Prints creation progress every configured number of screws. |

---

## How matching works

### 1. Read and classify geometry

The script reads geometry assemblies and parts, classifies wire bodies as screw candidates, and treats the remaining bodies as solid candidates. It reads wire-body vertices and the circular edges of the solid bodies.

### 2. Identify circular edges

Full circles are identified from their edge length and centroid. Their radius is calculated as:

`radius = edge length / (2 × π)`

For arc edges, the script determines the circle center, radius, and plane using either the closed-form method or the points-based method. The closed-form method is cross-checked against the points method for the first configured number of arcs; if a mismatch is found, the script switches to the points method.

### 3. Combine segmented circles

Arc segments from the same solid body are grouped when their fitted centers and radii agree within `CIRCLE_MATCH_TOL_MM` and their planes are parallel within the script's angular comparison. Accepted groups are treated as one circular target with all segment IDs retained.

### 4. Group screw line bodies and order their nodes

Line bodies sharing vertex positions are grouped into one screw. Coincident node positions are merged for matching while retaining the relevant vertex IDs and body references. The screw axis is estimated from the farthest pair of unique nodes, and nodes are ordered along that axis.

### 5. Match top, middle, and bottom nodes

- **Top:** The script searches for larger concentric edges at the screw ends and determines the top end using the configured rules and overrides.
- **Middle:** For each middle node, the smallest circular edge in the nearest concentric-edge cluster on each nearby solid body is considered. The configured maximum number of edges is applied.
- **Bottom:** The smallest circular edge in the nearest concentric-edge cluster on each nearby solid body is considered, with one edge assigned to the bottom node.

The candidate pairs are sorted by distance, edge radius, and edge ID before assignment. The distance tolerances and edge-use tracking prevent candidates outside the configured range or already assigned elsewhere from being used.

### 6. Check existing contacts and create missing ones

The script searches for the configured connection group and scans its contacts, including nested folders. It compares planned contacts with existing contact names and, when enabled, source/target geometry scopes. It then creates only the contacts that are not already present.

Contacts are created with Bonded contact type, MPC formulation, radius-based pinball, and the detected pinball radius. If creation of a contact fails after a partial object has been made, the script attempts to delete that partial object.

---

## Console report and troubleshooting

The console output is intended to be reviewed before and after creation.

| Report item | What to check |
|---|---|
| Wire bodies / solid bodies | Confirm that the expected geometry was classified. |
| Screws found and screw numbering | Confirm the number and order of screws. |
| Circular edges near screw nodes | Check that expected hole edges were detected. |
| Segmented arc groups | Confirm that split hole edges were combined as expected. |
| Rejected arc groups / unfit arcs | Review if a required hole was not accepted. |
| Top node / top edge checks | Review warnings where both ends qualify or no top candidate is found. |
| Matches and contacts per screw | Confirm the expected top, middle, and bottom assignments. |
| Existing contacts / to create | Confirm that reruns will not duplicate contacts. |
| Conflicting contacts | Review carefully before enabling automatic deletion. |
| Nodes without edge | These nodes need attention; the script may provide a nearby single-arc hint. |
| Failed contacts / property warnings | Inspect the reported contact name and API/property message. |
| Time per phase | Use to identify which processing stage takes the most time. |

### Common checks

**No screws detected**
- Confirm that screw geometry is represented by wire/line bodies.
- Confirm that the line bodies contain the expected vertices.
- Check that connected segments share coincident vertex positions.

**Hole edges are not detected**
- Confirm that the hole boundaries are circular edges on solid bodies.
- Check the model length units and the reported sample radius.
- Review `MIN_RADIUS_MM`, `END_TOL_MM`, `MID_TOL_MM`, and `PREFILTER_EDGES`.
- For segmented holes, review `INCLUDE_SEGMENTED_HOLES`, `MIN_ARCS_IN_CIRCLE`, and the arc-group report.

**A segmented hole is rejected or not grouped**
- Review the reported arc IDs and rejection reason.
- Check `CIRCLE_MATCH_TOL_MM` and `MIN_CIRCLE_COVERAGE`.
- If the closed-form arc calculation appears unsuitable for the geometry, set `ARC_METHOD = "points"` and compare the result.

**The wrong end is identified as the top**
- Review the warning in the top-node checks.
- Set `TOP_END_OVERRIDE` for the affected screw.
- If both ends qualify, review `TOP_COLLISION_RULE`.

**A contact is missing or duplicated**
- Check the existing-contact scan report.
- Confirm `GROUP_NAME` matches the intended connection group exactly.
- Keep `CHECK_EXISTING_BY_SCOPE = True` unless name-only matching is deliberately required.
- If the script reports that it cannot safely inspect existing contacts, resolve that issue before rerunning rather than forcing creation.

**The script is slow**
- Keep `PREFILTER_EDGES = True` and `ARC_METHOD = "closed_form"` unless troubleshooting indicates otherwise.
- Keep `FAST_EXISTING_SCAN = True` for large existing contact groups.
- Review the phase timing summary to identify the expensive stage.

---

## Important safety notes

- `DRY_RUN = True` is the default and should be used for the first run on every model.
- `DRY_RUN = False` permits model changes, including screw-body renaming when `RENAME_SCREWS_IN_TREE = True`, and contact creation.
- `REBUILD_FROM_SCRATCH = True` deletes the entire configured connection group, including folders and contacts.
- `DELETE_CONFLICTING_CONTACTS = True` can delete existing contacts. Review the conflict list and save a project copy before enabling it.
- The script's automatic geometric matching is based on tolerances and geometric heuristics. Always inspect the resulting scopes and contact regions.
- A successful script run does not establish that the resulting model is physically appropriate or that the analysis will converge.
- Save a backup copy of the project before running in creation mode, especially when using rebuild or conflict-deletion options.

---

## Repository contents

A simple repository layout could be:

```text
.
├── README.md
└── screwContactCreatorScript - v1.3.py
```

---

## Version history

### v1.3
- Added a fast closed-form arc geometry calculation based on chord length, arc length, and centroid.
- Cross-checks the first configured number of arcs against the points-based calculation and switches to the points method if a mismatch is detected.
- Added spatial prefiltering to discard circular edges far from all screw nodes.
- Optimized existing-contact scanning; planned contact names can be accepted without reading scopes when `FAST_EXISTING_SCAN` is enabled.
- Added phase-by-phase execution timing and progress timing.
- Improved connection-group name matching by normalizing case, spaces, underscores, and hyphens.
- Changed defaults to `DRY_RUN = True` and `REBUILD_FROM_SCRATCH = False` for safer execution.

### v1.2
- Reworked segmented circular-hole detection to group arcs by fitted circle center, radius, and plane orientation.
- Added circle-fit validation, minimum arc-count and circle-coverage checks, and improved arc-group reporting.

### v1.1
- Added rerun support and recognition of existing contacts by name and/or geometry scope.
- Added detection of conflicting contacts.
- Improved top-edge detection using concentric circular-edge groups and added top-edge overrides.
- Improved middle/bottom matching and console diagnostics.

### v1.0
- Initial automatic screw-node-to-hole-edge bonded MPC contact generation.
- Supported circular hole edges and the initial segmented-edge handling.

---

## License

No license is specified in this repository. Unless a license is added, standard copyright restrictions apply and reuse, modification, and redistribution are not automatically granted.

## Disclaimer

This script is provided as an engineering automation aid. It is not an official ANSYS product and is not affiliated with or endorsed by ANSYS, Inc. Use it at your own risk. The user is responsible for validating geometry selections, contact definitions, model behavior, and simulation results.
'''

output_path = "/mnt/data/README.md"
pypandoc.convert_text(readme, "md", format="md", outputfile=output_path, extra_args=["--standalone"])
print(f"Created {output_path}")
