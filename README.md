# Screw Contact Generator for Ansys Mechanical 2019 R2

An IronPython script that automatically creates the bonded MPC contacts between the nodes of 1D beam screws (line bodies) and the circular hole edges of the surrounding solid bodies. It also renames the screws in the geometry tree and gives every contact a consistent, traceable name.

**Version:** 1.4 | **Software:** Ansys Mechanical 2019 R2 (ACT Console, IronPython 2.7)



## Why this script exists

A model with hundreds of bolted joints needs at least four node-to-edge contacts per screw. Creating them by hand takes a very long time and is error-prone. The script finds the right edge for every screw node, sets the contact properties, and reports every node it could not handle so you can finish those by hand.

## Features

* Detects screws automatically: line bodies that share end points form one screw, and the nodes are ordered along the screw axis.
* Matches every node to its hole edge using a spatial grid, so large models stay fast.
* Supports full circular edges and hole edges split into several arcs (typical for STEP files). All arcs of a split edge become the contact target.
* Handles spacers: a middle or bottom node always uses the smallest concentric edge (the inner edge), regardless of the edge order in the geometry.
* Finds the top node by definition: an end node that has, around the hole edge, an extra concentric and larger edge.
* Creates only missing contacts on re-runs. An existing contact group, manual folders and contacts are never deleted.
* Renames the screws in the geometry tree (`Screw-0001`, `Screw-0002`, ...) in geometry-tree order.
* Prints a report with a list of nodes that need manual contacts.
* Includes a dry-run mode that changes nothing.

## Model assumptions

* Each screw is a chain of line bodies. Every section end is a geometry vertex (and therefore also a mesh node).
* Each screw sits in a hole made of two or three stacked solid bodies. The hole diameter may differ between bodies.
* **Top node:** an end node at the center of the hole edge, with an additional larger edge concentric to it on the outer face (perpendicular to the screw axis).
* **Middle nodes:** at the interface of two bodies, at the center of two circular edges (one per body).
* **Bottom node:** at the center of the hole edge of the last body.
* Hole edges are full circles or are split into several arcs.

## Contact definition

|Property|Value|
|-|-|
|Type|Bonded|
|Scope Mode|Manual|
|Contact side|Beam node (geometry vertex)|
|Target side|Circular edge (all arcs of a split edge)|
|Formulation|MPC|
|Constraint Type|Distributed, Anywhere Inside Pinball|
|Trim Contact|Program Controlled|
|Suppressed|No|
|Pinball Region|Radius|
|Pinball Radius|Edge radius + 0.3 mm|

> **Ansys 2019 R2 bug:** if the edge is selected before the node, the pinball center ends up on the edge and Contact Tool reports an open contact. The script always scopes the **node first and the edge(s) second**, and it can read the scope back after creation to confirm this (`VERIFY_SCOPE_AFTER_CREATE`). Please still check a few contacts with Contact Tool.

## Naming

|Object|Name|
|-|-|
|Screw (geometry tree)|`Screw-0001`, `Screw-0002`, ...|
|Contact|`Screw-0003 - TopEdge-6016`|
|Contact roles|`TopEdge`, `Mid1Edge`, `Mid2Edge`, ..., `BottomEdge`|
|Edge number|Edge id (lowest id for edges made of several arcs)|

Screws are numbered in geometry-tree order, top to bottom. The numbers change if the order in the tree changes.

## Requirements

* Ansys Mechanical 2019 R2 with the ACT Console.
* A model with line-body screws and solid bodies with circular hole edges.
* The Connection group (default name `screwContacts`) is created by the script if it does not exist. Folders inside it cannot be created through the 2019 R2 API; group them manually if you want them.

## How to run (Ansys 2019 R2)

1. **Back up** the project.
2. In Mechanical, turn on the **ACT** button in the toolbar to open the ACT Console.
3. Create a **new snippet**.
4. **Paste** the complete content of `screw_contacts.py` into the snippet.
5. **Click the snippet.** This pastes the code into the command line.
6. Press **Enter** to run it.

Recommended order:

1. Run with `DRY_RUN = True` and read the report.
2. Fix settings if needed, repeat the dry run.
3. Set `DRY_RUN = False` and run for real. Optionally test on a few screws first with `_SCREWS = [1, 3]`.
4. Create the nodes listed under "Nodes WITHOUT edge" by hand.
5. Check a few contacts with Contact Tool.

## Settings

All settings are at the top of the script.

### General

|Setting|Default|Meaning|
|-|-|-|
|`DRY_RUN`|`True`|`True`: plan and report only, change nothing. `False`: rename and create.|
|`PILOT_SCREWS`|`None`|List of screw numbers to process, e.g. `[1, 3]`. `None` = all screws.|
|`PINBALL_ADD_MM`|`0.3`|Added to the edge radius for the pinball radius.|
|`END_TOL_MM`|`3.0`|Maximum distance between a top or bottom node and the edge center.|
|`MID_TOL_MM`|`2.0`|Same for middle nodes. Keep it below half the screw spacing.|
|`MAX_EDGES_MID`|`2`|Edges per middle node (one per body).|
|`MID_LIMIT_OVERRIDE`|`{}`|Per node limit, e.g. `{(1, "MID2"): 1}`.|
|`MIN_RADIUS_MM`|`0.5`|Ignore circles smaller than this.|
|`LENGTH_FACTOR_TO_MM`|`None`|Automatic from the model unit. Set `1000.0` if the printed radius is wrong.|

### Existing contacts and re-runs

|Setting|Default|Meaning|
|-|-|-|
|`GROUP_NAME`|`"screwContacts"`|Name of the connection group. The name matching ignores case, spaces, `_` and `-`.|
|`REBUILD_FROM_SCRATCH`|`False`|`True` deletes the whole group, including folders and contacts.|
|`CHECK_EXISTING_BY_SCOPE`|`True`|Recognise existing contacts by name or by scope. `False` = by name only.|
|`FAST_EXISTING_SCAN`|`True`|Skip scope reading for contacts whose name matches a planned name.|
|`DELETE_CONFLICTING_CONTACTS`|`False`|Delete contacts that use a node of the script with a different edge. Review the list first.|
|`VERIFY_SCOPE_AFTER_CREATE`|`True`|Read back Source (node) and Target (edge) of each new contact and report mismatches.|

### Top node and top edge

|Setting|Default|Meaning|
|-|-|-|
|`TOP_END`|`"auto"`|`"auto"`, `"first"` or `"last"` along the screw axis.|
|`TOP_END_OVERRIDE`|`{}`|Per screw, e.g. `{7: "last"}`.|
|`TOP_COLLISION_RULE`|`"larger_edge"`|If both ends qualify: `"larger_edge"`, `"first"` or `"last"`.|
|`TOP_RULE`|`"closest_above_hole"`|Smallest edge larger than the hole, or `"largest"`.|
|`TOP_RADIUS_OVERRIDE`|`{}`|Per screw, e.g. `{7: 3.5}`.|
|`TOP_EDGE_OVERRIDE`|`{}`|Per screw, e.g. `{7: 5678}`. Any segment id of the edge works.|
|`TOP_MAX_RADIUS_MM`|`60.0`|Ignore larger circles at the top node.|
|`CONCENTRIC_TOL_MM`|`0.05`|Edges with centers closer than this are concentric.|
|`RADIUS_STEP_MIN_MM`|`0.05`|The extra edge must be at least this much larger than the hole edge.|

### Edges made of several arcs

|Setting|Default|Meaning|
|-|-|-|
|`INCLUDE_SEGMENTED_HOLES`|`True`|Combine arcs on the same circle into one hole edge.|
|`CIRCLE_MATCH_TOL_MM`|`0.05`|Arcs belong together if center and radius agree within this and the planes are parallel.|
|`MIN_ARCS_IN_CIRCLE`|`2`|A circle needs at least this many arcs. A single arc (for example a slot end) is not used.|
|`MIN_CIRCLE_COVERAGE`|`0.0`|Minimum fraction of the full circle covered by the arcs (0 = off).|
|`ARC_METHOD`|`"closed_form"`|`"closed_form"` or `"points"`. See the notes below.|
|`ARC_CROSSCHECK_N`|`3`|Number of arcs cross-checked between both methods.|

### Naming

|Setting|Default|Meaning|
|-|-|-|
|`SCREW_ORDER`|`"tree"`|`"tree"` = geometry-tree order, `"position"` = by coordinates.|
|`RENAME_SCREWS_IN_TREE`|`True`|Rename the screw line bodies in the tree.|
|`SCREW_PREFIX`|`"Screw-"`|Prefix of the screw name.|
|`SCREW_SEGMENT_SUFFIX`|`False`|Add `-Seg1`, `-Seg2`, ... if a screw has several bodies.|
|`NAME_SEPARATOR`|`" - "`|Separator inside contact names.|
|`INCLUDE_TREE_NAME_IN_CONTACT`|`False`|Old style tag from the original tree name. Switched off automatically when renaming is on.|
|`EXTRACT_FROM_PARENTHESES`|`False`|Only used with the tag: keep only the text inside `( )`.|

### Speed

|Setting|Default|Meaning|
|-|-|-|
|`PREFILTER_EDGES`|`True`|Drop edges that are far from every screw node early.|
|`FAST_PROPERTY_ORDER`|`True`|Properties first, scope last (fewer tree updates). `False`: scope first. Both select the node first.|
|`USE_TRANSACTION`|`True`|Use Mechanical's `Transaction` if it exists in this version.|
|`TX_BATCH_SCREWS`|`20`|Screws per transaction batch.|
|`SHOW_PHASE_TIMES`|`True`|Print the time of every phase in the summary.|

## How it works

1. **Read geometry.** Line bodies, their vertices and the circular edges of the solid bodies are read once from `GeoData` and converted to millimetres.
2. **Build the screws.** Line bodies sharing end positions are merged into one screw. Its nodes are ordered along the axis (farthest pair of nodes).
3. **Circular edges.** Full circles use the edge centroid as center and `length / 2π` as radius. Arcs have no radius or center property in 2019 R2, so they are computed: the arc angle follows from the chord, the arc length and the arc centroid, and a circle fit through the start vertex, a middle point and the end vertex is used as a cross-check. Arcs of the same body with the same center, radius and plane form one hole edge.
4. **Spatial grid.** Edges are stored in 3D grid cells so each node only checks its own cell and its neighbours.
5. **Match.** For each node and body the nearest cluster of concentric edges is taken, and the smallest circle is the hole edge. The top node is the end that has a larger concentric edge as well. Every edge is used only once.
6. **Contacts.** Missing contacts are created screw by screw (top, middle nodes, bottom), so one screw's contacts are listed together. Node first, then edge(s).

## The report

|Section|What it tells you|
|-|-|
|Header|Mode (dry run or create), unit, counts of bodies and edges|
|Hole edges made of several arcs|Arc ids, covered fraction of the circle, radius, center|
|`[rejected]`|Arc groups that were not used and why|
|Top node checks|Candidates for the top edge and warnings if both ends qualify|
|Screw numbering|New name next to the original tree name|
|Contacts per screw|Number of contacts per role|
|Existing contacts|How many were found and recognised, `[?]` for contacts that conflict with the plan|
|Summary|Created and failed contacts, scope check, timing|
|`Nodes WITHOUT edge`|Nodes you must connect manually, with a reason|

## Limitations

* Hole edges must be full circles or arcs of one circle. Slots, pill shapes and single half circles are not supported and are listed as missing.
* Folders inside the contact group cannot be created through the 2019 R2 API. New contacts are added at the end of the group; move them into your manual folders if needed.
* Screw numbers follow the geometry tree order. If the order changes, numbers and names change on the next run.
* Renaming, tree order, `Transaction` and some property names depend on the API of the installed version. Failures are printed and do not stop the run.
* The script was developed and tested on a sample model with 20 screws. Test on a few screws (`PILOT_SCREWS`) before running on a new model type.

## Troubleshooting

|Problem|Likely cause and fix|
|-|-|
|Nothing is renamed or created|`DRY_RUN` is `True`. Set it to `False`.|
|A second contact group appears|`GROUP_NAME` does not match the name of your existing group. The report lists the objects under Connections.|
|`Creation skipped` message|The existing group could not be read safely. Nothing is created to avoid duplicates.|
|Radius is 1000 times off|Set `LENGTH_FACTOR_TO_MM`.|
|Node listed under `NO EDGE`|The edge is not circular, is a single arc, or lies outside the tolerance. Create the contact by hand or increase the tolerance.|
|Wrong top edge|Use `TOP_END_OVERRIDE`, `TOP_RADIUS_OVERRIDE` or `TOP_EDGE_OVERRIDE` for that screw.|
|Open contact in Contact Tool|Check `Scope check` in the summary. The node must be the contact side and must be selected first.|
|Message about switching to the Points method|The closed form for arcs did not match the Points method. The script uses Points automatically.|

## Repository files

|File|Purpose|
|-|-|
|`screw_contacts.py`|The script|
|`README.md`|This file|

## Version history

|Version|Change|
|-|-|
|1.4|Node is always scoped first, then the edge(s). Scope read-back check after creation.|
|1.3|Closed-form arc geometry, edge prefilter, faster existing-contact scan, phase timing.|
|1.2|True radius and center for arcs, grouping of arcs on one circle, minimum arcs per circle.|
|1.1|Re-runs create only missing contacts. Spacer fix (inner edge). Top node by definition.|
|1.0|First release: node-to-edge contacts, tree renaming, per-screw order, report.|

## License

This project is licensed under the MIT License.

## Disclaimer

Check the results before using them in a simulation. Always keep a backup of the project and verify a sample of the generated contacts.

