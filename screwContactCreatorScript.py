# -*- coding: utf-8 -*-
# =====================================================================
#  Screw Contact Generator  v1.4
#  Ansys Mechanical 2019 R2 (ACT Console, IronPython 2.7)
#
#  Creates bonded MPC contacts between beam-screw nodes (line bodies)
#  and the circular hole edges (full circles or sets of arcs) of the
#  surrounding solid bodies. Screws and contacts are named consistently.
#  Re-runs only add missing contacts; the existing group, folders and
#  contacts are kept.
#
#  Contact : beam node (vertex) is scoped FIRST, then the target edge(s)
#  Pinball : edge radius + 0.3 mm
#  Naming  : Screw-0001 (geometry tree order), "Screw-0001 - TopEdge-6016"
#
#  Usage   : run with DRY_RUN = True first, check the console report.
#  Details : see README.md
# =====================================================================
SCRIPT_VERSION = "1.4"
import math
import re
import time
import System

T_SCRIPT_START = time.time()
phase_times = []
_phase_mark = [time.time()]

def phase(name):
    now = time.time()
    phase_times.append((name, now - _phase_mark[0]))
    _phase_mark[0] = now

# ======================= USER SETTINGS =======================
DRY_RUN          = True    # True: only report matches and planned changes, change nothing
PILOT_SCREWS     = None    # e.g. [1, 3] = only these screws; None = ALL screws (no limit)
PINBALL_ADD_MM   = 0.3     # added to edge radius
END_TOL_MM       = 3.0     # max distance node <-> edge center for top/bottom node
MID_TOL_MM       = 2.0     # max distance node <-> edge center for middle nodes
MAX_EDGES_MID    = 2       # edges per middle node (one per different body)
MID_LIMIT_OVERRIDE = {}    # e.g. {(1, "MID2"): 1} -> screw 1, node MID2 gets only 1 edge
MIN_RADIUS_MM    = 0.5     # ignore tiny circles
LENGTH_FACTOR_TO_MM = None # None = auto from GeoData.Unit. Set 1000.0 if API returns metres

# ---- existing contacts (re-runs) ----
GROUP_NAME       = "screwContacts"   # exact name of your existing group
REBUILD_FROM_SCRATCH = False   # True: delete the whole group (with folders and contacts!) first
CHECK_EXISTING_BY_SCOPE = True # True: existing contacts are recognised by name OR scope
                               # False: by name only (faster, but renamed contacts are not found)
FAST_EXISTING_SCAN = True      # True: a contact whose name equals a planned name is accepted
                               #       without reading its scope (much faster for large groups)
DELETE_CONFLICTING_CONTACTS = False  # True: delete contacts that use a node of this script with
                                     # an edge the script does not select (review the list first!)
LIST_NEW_CONTACTS = True       # print the names of newly created contacts
LIST_NEW_MAX      = 100        # max number of names printed

# ---- scope assignment (Ansys 2019 R2 bug: the node must be selected first) ----
VERIFY_SCOPE_AFTER_CREATE = True   # True: read back Source (node) and Target (edge) of every new
                                   #       contact and report any mismatch

# ---- top node / top edge ----
TOP_END          = "auto"  # "auto" = detect by definition, or "first" / "last" (axis order)
TOP_END_OVERRIDE = {}      # e.g. {7: "last"} -> screw 7 top end forced
TOP_COLLISION_RULE = "larger_edge"  # both ends have an extra edge: "larger_edge", "first", "last"
TOP_RULE         = "closest_above_hole"   # smallest edge larger than the hole, or "largest"
TOP_RADIUS_OVERRIDE = {}   # e.g. {7: 3.5} -> screw 7 top edge radius 3.5 mm
TOP_EDGE_OVERRIDE   = {}   # e.g. {7: 5678} -> screw 7 top edge with this edge id (any segment id)
TOP_MAX_RADIUS_MM= 60.0    # ignore circular edges larger than this at the top node
CONCENTRIC_TOL_MM  = 0.05  # edges with centers closer than this are "concentric"
RADIUS_STEP_MIN_MM = 0.05  # an extra edge must be larger than the hole edge by at least this

# ---- arcs of one circle (typical for STEP: a hole edge split into several segments) ----
INCLUDE_SEGMENTED_HOLES = True   # True: arcs on the same circle are combined into ONE hole edge
                                 #       and ALL of them become the contact target
                                 # False: only full single-edge circles are used
CIRCLE_MATCH_TOL_MM  = 0.05      # arcs belong to the same circle if center and radius agree within
                                 # this tolerance and their planes are parallel
MIN_ARCS_IN_CIRCLE   = 2         # a circle needs at least this many arcs (1 = also single arcs)
MIN_CIRCLE_COVERAGE  = 0.0       # minimum part of the full circle covered by the arcs
                                 # (0 = off, 0.5 = at least 50 %)
ARC_FIT_TOL_FRAC     = 0.02      # (points method) arc points must lie on the fitted circle
                                 # within this fraction of r
LIST_ARC_GROUPS_MAX  = 30        # max number of arc groups listed in the report

# ---- screw numbering and naming ----
SCREW_ORDER      = "tree"       # "tree" = numbered in geometry-tree order (top to bottom)
                                # "position" = numbered by X, Y, Z position of the screw
RENAME_SCREWS_IN_TREE = True    # True: rename the screw line bodies in the geometry tree
SCREW_PREFIX          = "Screw-"        # screw name = prefix + 4-digit number -> "Screw-0001"
SCREW_SEGMENT_SUFFIX  = False   # True: several bodies of one screw -> "Screw-0001-Seg1", ...

# ---- contact naming ----
NAME_SEPARATOR   = " - "        # between the name parts: "Screw-0003 - TopEdge-6016"
# Old style: add a tag taken from the ORIGINAL geometry tree name to the contact name.
# It is switched off automatically when RENAME_SCREWS_IN_TREE is True.
INCLUDE_TREE_NAME_IN_CONTACT = False
EXTRACT_FROM_PARENTHESES     = False   # only used when the tag is included:
                                       # True = keep only the text inside (...)

# ---- speed ----
PREFILTER_EDGES     = True   # True: edges whose center is not near any screw node are dropped early
PREFILTER_MARGIN_MM = 0.5    # extra margin for the prefilter
ARC_METHOD          = "closed_form"   # "closed_form" (fast, no Points call) or "points"
ARC_CROSSCHECK_N    = 3      # closed form is compared with the Points method for this many arcs;
                             # on a mismatch the script switches to "points" automatically
FAST_PROPERTY_ORDER = True   # True: scope is assigned last (fewer updates). False: scope first
USE_TRANSACTION     = True   # True: use Mechanical's Transaction (if it exists in this version)
TX_BATCH_SCREWS     = 20     # screws per transaction batch
SHOW_TIMING         = True   # print elapsed time and estimate in the progress lines
SHOW_PHASE_TIMES    = True   # print the time of every phase in the summary

VERBOSE_MATCHES  = False   # True: print every single match
PROGRESS_EVERY   = 25      # progress line every N screws while creating
# =============================================================

USE_TAG = INCLUDE_TREE_NAME_IN_CONTACT and not RENAME_SCREWS_IN_TREE

print("Screw Contact Generator v%s" % SCRIPT_VERSION)
print("MODE: %s | PILOT_SCREWS = %s | SCREW_ORDER = %s | INCLUDE_SEGMENTED_HOLES = %s"
      % ("DRY RUN (nothing will be changed)" if DRY_RUN else "CREATE MISSING CONTACTS",
         PILOT_SCREWS, SCREW_ORDER, INCLUDE_SEGMENTED_HOLES))
if INCLUDE_TREE_NAME_IN_CONTACT and RENAME_SCREWS_IN_TREE:
    print("NOTE: RENAME_SCREWS_IN_TREE is True -> tree-name tag is NOT added to contact names")
if EXTRACT_FROM_PARENTHESES and not USE_TAG:
    print("NOTE: EXTRACT_FROM_PARENTHESES has no effect (the tree-name tag is not used)")
if REBUILD_FROM_SCRATCH:
    print("NOTE: REBUILD_FROM_SCRATCH = True -> the group '%s' is deleted with ALL its folders "
          "and contacts" % GROUP_NAME)

geo = ExtAPI.DataModel.GeoData
model = ExtAPI.DataModel.Project.Model

def dist(a, b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)

def pos_text(p):
    return "(%.2f, %.2f, %.2f)" % (p[0], p[1], p[2])

# ---------- unit factor ----------
if LENGTH_FACTOR_TO_MM is None:
    umap = {"m": 1000.0, "mm": 1.0, "cm": 10.0, "um": 0.001, "in": 25.4, "ft": 304.8}
    try:
        u = str(geo.Unit).strip().lower()
        F = umap.get(u, 1000.0)
        print("GeoData unit = '%s' -> factor to mm = %s" % (u, F))
    except:
        F = 1000.0
        print("GeoData.Unit not readable, assuming metres (factor 1000)")
else:
    F = LENGTH_FACTOR_TO_MM

# ---------- vector helpers ----------
def v_sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def v_dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def v_cross(a, b):
    return (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])

def v_len(a):
    return math.sqrt(v_dot(a, a))

def circle_from_3(A, B, C):
    """Circle through three 3D points -> (center, radius, unit normal), or None if collinear."""
    a = v_sub(A, C)
    b = v_sub(B, C)
    axb = v_cross(a, b)
    la, lb, lab = v_len(a), v_len(b), v_len(axb)
    if lab == 0.0 or lab <= 1e-6 * la * lb:
        return None
    t1 = (b[0]*la*la - a[0]*lb*lb, b[1]*la*la - a[1]*lb*lb, b[2]*la*la - a[2]*lb*lb)
    q = v_cross(t1, axb)
    k = 1.0 / (2.0 * lab * lab)
    ctr = (C[0] + q[0]*k, C[1] + q[1]*k, C[2] + q[2]*k)
    r = la * lb * v_len(v_sub(A, B)) / (2.0 * lab)
    nrm = (axb[0]/lab, axb[1]/lab, axb[2]/lab)
    return ctr, r, nrm

# ---------- edge helpers (radius/center of arcs are NOT available from the API) ----------
def edge_ends(e):
    """(closed, start point, end point) in mm. closed = full circle (start = end)."""
    try:
        sv, ev = e.StartVertex, e.EndVertex
        if sv is None or ev is None or sv.Id == ev.Id:
            return True, None, None
        pA = (sv.X * F, sv.Y * F, sv.Z * F)
        pC = (ev.X * F, ev.Y * F, ev.Z * F)
        if dist(pA, pC) < 1e-3:
            return True, None, None
        return False, pA, pC
    except:
        return True, None, None

def edge_points(e):
    """Points on the edge as [(x, y, z)] in mm, or None."""
    try:
        flat = list(e.Points)
    except:
        return None
    if len(flat) < 9 or len(flat) % 3 != 0:
        return None
    return [(flat[i] * F, flat[i+1] * F, flat[i+2] * F) for i in range(0, len(flat), 3)]

def fit_arc(e, pA, pC):
    """Points method: circle through start vertex, a middle point and end vertex.
    Returns (center, radius, normal, worst deviation of the other points) or None."""
    pts = edge_points(e)
    if pts is None or len(pts) < 3:
        return None
    pB = pts[len(pts) // 2]
    res = circle_from_3(pA, pB, pC)
    if res is None:
        return None
    ctr, r, nrm = res
    worst = max([abs(dist(p, ctr) - r) for p in pts])
    return ctr, r, nrm, worst

def arc_closed_form(pA, pC, L, G):
    """Closed form from chord (start-end), arc length L and arc centroid G (no Points call).
    c/L = sin(a/2)/(a/2) gives the arc angle a, r = L/a; the center lies on the line from the
    chord midpoint M through G, at distance r*cos(a/2) from M, on the side away from the arc.
    Returns (center, radius, normal, 0.0) or None when the result would be unreliable."""
    chord = dist(pA, pC)
    if chord < 1e-6 or L <= 0.0:
        return None
    ratio = chord / L
    if ratio >= 0.99999 or ratio <= 1e-6:
        return None
    lo, hi = 1e-6, math.pi - 1e-9
    for _i in range(60):
        mid = 0.5 * (lo + hi)
        if math.sin(mid) / mid > ratio:
            lo = mid
        else:
            hi = mid
    x = 0.5 * (lo + hi)               # half of the arc angle
    r = L / (2.0 * x)
    M = ((pA[0] + pC[0]) / 2.0, (pA[1] + pC[1]) / 2.0, (pA[2] + pC[2]) / 2.0)
    GM = v_sub(G, M)
    lg = v_len(GM)
    if lg < 0.002 * r or lg < 1e-4:   # direction M->G too noisy (very small arc)
        return None
    u = (GM[0] / lg, GM[1] / lg, GM[2] / lg)
    cx = math.cos(x)
    ctr = (M[0] - r * cx * u[0], M[1] - r * cx * u[1], M[2] - r * cx * u[2])
    nv = v_cross(v_sub(pC, pA), GM)
    ln = v_len(nv)
    if ln < 1e-9:
        return None
    return ctr, r, (nv[0] / ln, nv[1] / ln, nv[2] / ln), 0.0

arc_state = {"method": "points" if ARC_METHOD == "points" else "closed_form",
             "checked": 0, "wc": 0.0, "wr": 0.0, "switched": False}

def arc_geometry(e, pA, pC, L, G):
    """Center, radius, normal of an arc. Closed form first (fast); the first arcs are
    cross-checked with the Points method, and a mismatch switches to the Points method."""
    if arc_state["method"] == "points":
        return fit_arc(e, pA, pC)
    cf = arc_closed_form(pA, pC, L, G)
    if arc_state["checked"] < ARC_CROSSCHECK_N:
        pf = fit_arc(e, pA, pC)
        arc_state["checked"] += 1
        if cf is not None and pf is not None:
            dc = dist(cf[0], pf[0])
            dr = abs(cf[1] - pf[1])
            arc_state["wc"] = max(arc_state["wc"], dc)
            arc_state["wr"] = max(arc_state["wr"], dr)
            if dc > CIRCLE_MATCH_TOL_MM or dr > CIRCLE_MATCH_TOL_MM:
                arc_state["method"] = "points"
                arc_state["switched"] = True
        return pf if pf is not None else cf
    if cf is None:
        return fit_arc(e, pA, pC)
    return cf

def group_arcs(body_id, arcs):
    """All arcs of ONE body with the same center, radius and plane form one hole edge.
    Returns (circles, single_arc_groups, rejected_groups)."""
    n = len(arcs)
    par = list(range(n))
    def fnd(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    def same_circle(a, b):
        if abs(a["r"] - b["r"]) > CIRCLE_MATCH_TOL_MM:
            return False
        if dist(a["c"], b["c"]) > CIRCLE_MATCH_TOL_MM:
            return False
        return abs(v_dot(a["n"], b["n"])) >= 0.999
    cell = max(2.0 * CIRCLE_MATCH_TOL_MM, 0.1)
    def ckey(c):
        return (int(math.floor(c[0] / cell)), int(math.floor(c[1] / cell)), int(math.floor(c[2] / cell)))
    bucket = {}
    for i in range(n):
        bucket.setdefault(ckey(arcs[i]["c"]), []).append(i)
    for i in range(n):
        kx, ky, kz = ckey(arcs[i]["c"])
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in bucket.get((kx + dx, ky + dy, kz + dz), []):
                        if j > i and same_circle(arcs[i], arcs[j]):
                            par[fnd(i)] = fnd(j)
    comps = {}
    for i in range(n):
        comps.setdefault(fnd(i), []).append(arcs[i])
    circles = []
    singles = []
    rejected = []
    for comp in comps.values():
        ids = sorted([x["id"] for x in comp])
        Ltot = sum([x["len"] for x in comp])
        ctr = tuple([sum([x["len"] * x["c"][k] for x in comp]) / Ltot for k in range(3)])
        rad = sum([x["len"] * x["r"] for x in comp]) / Ltot
        cov = sum([x["alpha"] for x in comp]) / (2.0 * math.pi)
        if len(comp) < MIN_ARCS_IN_CIRCLE:
            singles.append({"body": body_id, "ids": ids, "r": rad, "c": ctr, "cov": cov})
            continue
        if cov < MIN_CIRCLE_COVERAGE:
            rejected.append((body_id, ids, rad, "arcs cover only %.0f %% of a full circle (minimum %.0f %%)"
                             % (100.0 * cov, 100.0 * MIN_CIRCLE_COVERAGE)))
            continue
        circles.append({"id": ids[0], "ids": ids, "body": body_id, "c": ctr, "r": rad,
                        "split": True, "cov": cov, "narcs": len(comp)})
    return circles, singles, rejected

def eid_text(e):
    """Edge id text; edges made of several arcs show all ids, e.g. 6016+6017."""
    return "+".join([str(i) for i in e["ids"]])

# ---------- read geometry ----------
wire_bodies = []   # dict(id, verts=[(id,(x,y,z))], name, part)
solid_bodies = []  # solid body objects
circ_edges  = []   # dict(id, ids, body, c=(x,y,z) mm, r mm, split, cov, narcs)
skipped_arcs = 0       # arcs ignored because INCLUDE_SEGMENTED_HOLES = False
unfit_arcs = 0         # arcs whose circle could not be determined
full_circles = 0
n_prefiltered = 0      # circular edges dropped because no screw node is near
split_list = []        # hole edges made of several arcs
single_list = []       # arc groups with too few arcs (not used)
rejected_groups = []

def is_wire(b):
    try:
        return b.BodyType == GeoBodyTypeEnum.GeoBodyWire
    except:
        return len(b.Faces) == 0 and len(b.Edges) > 0

# pass 1: line bodies (screws) and list of solid bodies
for asm in geo.Assemblies:
    for part in asm.Parts:
        for body in part.Bodies:
            if is_wire(body):
                vs = [(v.Id, (v.X * F, v.Y * F, v.Z * F)) for v in body.Vertices]
                try:
                    bname = str(body.Name)
                except:
                    bname = ""
                try:
                    pname = str(part.Name)
                except:
                    pname = ""
                wire_bodies.append({"id": body.Id, "verts": vs, "name": bname, "part": pname})
            else:
                solid_bodies.append(body)

# grid of all screw nodes, used to drop edges that are far from every node
PRE_TOL = max(END_TOL_MM, MID_TOL_MM) + PREFILTER_MARGIN_MM

def cell_key(p, cell):
    return (int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell)), int(math.floor(p[2] / cell)))

node_grid = {}
for wb in wire_bodies:
    for vid, p in wb["verts"]:
        node_grid.setdefault(cell_key(p, PRE_TOL), []).append(p)

def near_any_node(c):
    kx, ky, kz = cell_key(c, PRE_TOL)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for p in node_grid.get((kx + dx, ky + dy, kz + dz), []):
                    if dist(p, c) <= PRE_TOL:
                        return True
    return False

use_prefilter = PREFILTER_EDGES and len(node_grid) > 0

# pass 2: circular edges of the solid bodies
for body in solid_bodies:
    arcs_in_body = []
    for e in body.Edges:
        try:
            if e.CurveType != GeoCurveTypeEnum.GeoCurveCircle:
                continue
            L = e.Length * F
            cen = e.Centroid
            cc = (cen[0] * F, cen[1] * F, cen[2] * F)
            closed, pA, pC = edge_ends(e)
            if closed:
                # full circle: centroid = circle center, radius from the length
                r = L / (2 * math.pi)
                if r < MIN_RADIUS_MM:
                    continue
                if use_prefilter and not near_any_node(cc):
                    n_prefiltered += 1
                    continue
                circ_edges.append({"id": e.Id, "ids": [e.Id], "body": body.Id,
                                   "c": cc, "r": r, "split": False, "cov": 1.0, "narcs": 1})
                full_circles += 1
            elif not INCLUDE_SEGMENTED_HOLES:
                skipped_arcs += 1
            else:
                fit = arc_geometry(e, pA, pC, L, cc)
                if fit is None:
                    unfit_arcs += 1
                    continue
                ctr, r, nrm, worst = fit
                if r < MIN_RADIUS_MM:
                    continue
                if worst > max(0.005, ARC_FIT_TOL_FRAC * r):
                    unfit_arcs += 1
                    continue
                if use_prefilter and not near_any_node(ctr):
                    n_prefiltered += 1
                    continue
                alpha = L / r
                if alpha >= 2 * math.pi * 0.98:
                    circ_edges.append({"id": e.Id, "ids": [e.Id], "body": body.Id,
                                       "c": ctr, "r": r, "split": False, "cov": 1.0, "narcs": 1})
                    full_circles += 1
                else:
                    arcs_in_body.append({"id": e.Id, "r": r, "len": L, "c": ctr,
                                         "n": nrm, "alpha": alpha})
        except:
            pass
    if arcs_in_body:
        circles, singles, rej = group_arcs(body.Id, arcs_in_body)
        for ci in circles:
            circ_edges.append(ci)
            split_list.append(ci)
        single_list.extend(singles)
        rejected_groups.extend(rej)

n_split_arcs = sum([ci["narcs"] for ci in split_list])
print("Line bodies: %d | solid bodies: %d | circular edges near screw nodes: %d "
      "(full: %d, made of arcs: %d from %d arcs)"
      % (len(wire_bodies), len(solid_bodies), len(circ_edges), full_circles, len(split_list), n_split_arcs))
print("Single arcs not used: %d | rejected arc groups: %d | arcs not determined: %d | "
      "circular edges dropped by the prefilter (far from every node): %d"
      % (len(single_list), len(rejected_groups), unfit_arcs, n_prefiltered))
if not wire_bodies:
    print("  [!] no line bodies found -> nothing to do")
if INCLUDE_SEGMENTED_HOLES:
    if arc_state["switched"]:
        print("  [!] Arc geometry: the closed form differed from the Points method by up to %.3f mm "
              "(centers) / %.3f mm (radii) -> switched to the Points method for all arcs"
              % (arc_state["wc"], arc_state["wr"]))
    elif arc_state["method"] == "points":
        print("Arc geometry: Points method (ARC_METHOD = 'points')")
    elif arc_state["checked"]:
        print("Arc geometry: closed form (cross-checked %d arcs against the Points method: "
              "max center difference %.4f mm, max radius difference %.4f mm)"
              % (arc_state["checked"], arc_state["wc"], arc_state["wr"]))
if skipped_arcs:
    print("NOTE: %d arcs ignored (INCLUDE_SEGMENTED_HOLES = False)" % skipped_arcs)
if unfit_arcs:
    print("NOTE: %d arcs could not be determined (degenerate or no usable points) -> not used"
          % unfit_arcs)
if split_list:
    print("--- hole edges made of several arcs: %d ---" % len(split_list))
    for ci in split_list[:LIST_ARC_GROUPS_MAX]:
        print("  body %s edges %s | %d arcs, %.0f %% of circle | r=%.3f mm | center %s"
              % (ci["body"], eid_text(ci), ci["narcs"], 100.0 * ci["cov"], ci["r"], pos_text(ci["c"])))
    if len(split_list) > LIST_ARC_GROUPS_MAX:
        print("  ... and %d more" % (len(split_list) - LIST_ARC_GROUPS_MAX))
for rj in rejected_groups:
    print("  [rejected] body %s edges %s r=%.3f mm: %s"
          % (rj[0], "+".join([str(i) for i in rj[1]]), rj[2], rj[3]))
if circ_edges:
    print("Sample edge radius [mm] (check units!): %.4f" % circ_edges[0]["r"])
phase("read geometry (bodies and edges)")

def single_hint(p, tol):
    """Text about single arcs (not used) near position p."""
    out = []
    for s in single_list:
        if dist(p, s["c"]) <= tol:
            out.append("edge %s (r=%.3f, only %d arc)" % ("+".join([str(i) for i in s["ids"]]),
                                                         s["r"], len(s["ids"])))
    return ", ".join(out[:3])

# ---------- read the geometry tree (body order + tree objects) ----------
tree_list = []     # [(geoBodyId, treeObject)] in tree order
try:
    for tb in model.Geometry.GetChildren(DataModelObjectCategory.Body, True):
        try:
            tree_list.append((tb.GetGeoBody().Id, tb))
        except:
            pass
except Exception as ex:
    print("  [!] could not read the geometry tree (%s)" % ex)

tree_by_id = {}
tree_index = {}
for k, (gid, tb) in enumerate(tree_list):
    tree_by_id[gid] = tb
    tree_index[gid] = k

if SCREW_ORDER == "tree":
    if tree_index:
        print("Screw numbering follows the geometry tree order (%d tree bodies read)" % len(tree_index))
    else:
        print("  [!] tree order not available -> using the order of the geometry database "
              "(normally the same as the tree)")

def body_rank(b):
    gid = wire_bodies[b]["id"]
    if gid in tree_index:
        return tree_index[gid]
    return 1000000 + b          # fallback: geometry database order

# ---------- group wire bodies into screws (shared positions) ----------
def key(p, q=0.01):
    return (round(p[0] / q), round(p[1] / q), round(p[2] / q))

parent = list(range(len(wire_bodies)))
def find(i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i

pos_owner = {}
for i, wb in enumerate(wire_bodies):
    for vid, p in wb["verts"]:
        k = key(p)
        if k in pos_owner:
            parent[find(i)] = find(pos_owner[k])
        else:
            pos_owner[k] = i

screws = {}
for i, wb in enumerate(wire_bodies):
    screws.setdefault(find(i), []).append(i)

# nodes of each screw: unique positions, with all vertex ids and bodies at that position
screw_list = []
for root, idxs in screws.items():
    nodes = {}
    for i in idxs:
        for vid, p in wire_bodies[i]["verts"]:
            k = key(p)
            if k not in nodes:
                nodes[k] = {"p": p, "vids": [], "bodies": []}
            nodes[k]["vids"].append(vid)
            if i not in nodes[k]["bodies"]:
                nodes[k]["bodies"].append(i)
    nl = list(nodes.values())
    if len(nl) < 2:
        continue
    # axis = farthest pair
    best = (-1, None, None)
    for a in nl:
        for b in nl:
            d = dist(a["p"], b["p"])
            if d > best[0]:
                best = (d, a, b)
    A, B = best[1]["p"], best[2]["p"]
    ax = [B[j] - A[j] for j in range(3)]
    for n in nl:
        n["t"] = sum([(n["p"][j] - A[j]) * ax[j] for j in range(3)])
    nl.sort(key=lambda n: n["t"])
    screw_list.append(nl)

def screw_tree_rank(nl):
    """Earliest position in the geometry tree of any body of this screw."""
    return min([body_rank(b) for nd in nl for b in nd["bodies"]])

# screw numbering
if SCREW_ORDER == "tree":
    screw_list.sort(key=lambda nl: (screw_tree_rank(nl),
                                    round(nl[0]["p"][0], 1), round(nl[0]["p"][1], 1),
                                    round(nl[0]["p"][2], 1)))
else:
    screw_list.sort(key=lambda nl: (round(nl[0]["p"][0], 1), round(nl[0]["p"][1], 1),
                                    round(nl[0]["p"][2], 1)))
print("Screws found: %d" % len(screw_list))
phase("read tree, group and number screws")

# ---------- helpers for screw names ----------
def clean_name(s):
    """Remove spaces and special characters, capitalise the first letter."""
    out = "".join([ch for ch in s if ch.isalnum()])
    return out[:1].upper() + out[1:]

def body_label(b):
    """Original geometry-tree name of a line body (falls back to part name, then body id)."""
    wb = wire_bodies[b]
    return wb["name"] or wb["part"] or ("body%s" % wb["id"])

def screw_bodies_tree_order(si):
    """Body indices of screw si, in geometry-tree order."""
    bs = set()
    for nd in screw_list[si]:
        for b in nd["bodies"]:
            bs.add(b)
    return sorted(bs, key=body_rank)

def screw_tag(si):
    """Original tree name of the first body (in tree order) of screw si."""
    return body_label(screw_bodies_tree_order(si)[0])

def extract_tag(full_name):
    """Text inside the last (...) of the name; whole name if there are no parentheses."""
    if EXTRACT_FROM_PARENTHESES:
        groups = [g.strip() for g in re.findall(r"\(([^()]*)\)", full_name)]
        groups = [g for g in groups if g]
        if groups:
            return groups[-1]
    return full_name

def contact_tag(si):
    """Short tag from the original tree name (only used if USE_TAG)."""
    t = clean_name(extract_tag(screw_tag(si)))
    if not t:
        t = clean_name(screw_tag(si))
    return t

def screw_name(si):
    """New screw name, same number as in the report: Screw-0001"""
    return "%s%04d" % (SCREW_PREFIX, si + 1)

def screw_bodies_ordered(si):
    """Body indices of screw si, ordered along the screw axis."""
    order = []
    for nd in screw_list[si]:
        for b in nd["bodies"]:
            if b not in order:
                order.append(b)
    return order

def select_screw(n):
    """Highlight screw number n in the graphics window (use from the console)."""
    ids = set()
    for nd in screw_list[n - 1]:
        for b in nd["bodies"]:
            ids.add(wire_bodies[b]["id"])
    sel = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    sel.Ids = list(ids)
    ExtAPI.SelectionManager.NewSelection(sel)
    try:
        ExtAPI.Graphics.Camera.SetFit()
    except:
        pass

# ---------- spatial grid for edges ----------
CELL = max(END_TOL_MM, MID_TOL_MM)
grid = {}
for e in circ_edges:
    c = e["c"]
    grid.setdefault((int(math.floor(c[0]/CELL)), int(math.floor(c[1]/CELL)), int(math.floor(c[2]/CELL))), []).append(e)

def near_edges(p, tol):
    out = []
    cx, cy, cz = int(math.floor(p[0]/CELL)), int(math.floor(p[1]/CELL)), int(math.floor(p[2]/CELL))
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for e in grid.get((cx+dx, cy+dy, cz+dz), []):
                    d = dist(p, e["c"])
                    if d <= tol:
                        out.append((d, e))
    return out

def body_clusters(p, tol):
    """For node position p: per body the nearest cluster of CONCENTRIC circular edges
    (edge centers within CONCENTRIC_TOL_MM of the nearest edge center), sorted by radius.
    edges[0] is the smallest circle = the hole edge of that body at this position."""
    by_body = {}
    for d, e in near_edges(p, tol):
        by_body.setdefault(e["body"], []).append((d, e))
    out = []
    for bid, lst in by_body.items():
        lst.sort(key=lambda x: (round(x[0], 4), x[1]["r"], x[1]["id"]))
        anchor = lst[0][1]
        cl = [(d, e) for d, e in lst if dist(e["c"], anchor["c"]) <= CONCENTRIC_TOL_MM]
        cl.sort(key=lambda x: (x[1]["r"], x[1]["id"]))
        out.append({"body": bid, "d": lst[0][0], "edges": cl})
    return out

def top_extras(p):
    """Extra edges of an END node: edges concentric with the hole edge of the same body,
    larger than the hole edge (same plane, perpendicular to the beam axis).
    Returns [(distance, edge, hole_edge)]; empty list = this end is not a top candidate."""
    res = []
    for cl in body_clusters(p, END_TOL_MM):
        es = cl["edges"]
        hole = es[0][1]
        for d, e in es[1:]:
            if e["r"] > hole["r"] + RADIUS_STEP_MIN_MM and e["r"] <= TOP_MAX_RADIUS_MM:
                res.append((d, e, hole))
    return res

used = set()
matches = []     # (screw_idx, node_label, node, edge, dist)
unmatched = []   # (screw_idx, node_label, position, reason, node)
roles = []       # per screw: (top, bottom, mids)

# ---------- 1) top nodes ----------
print("--- top node / top edge checks ---")
for si, nl in enumerate(screw_list):
    sn = si + 1
    first, last = nl[0], nl[-1]
    ex_first = top_extras(first["p"])
    ex_last = top_extras(last["p"])
    mode = TOP_END_OVERRIDE.get(sn, TOP_END)
    no_extra_anywhere = False
    if mode == "first":
        top, bot = first, last
    elif mode == "last":
        top, bot = last, first
    elif ex_first and not ex_last:
        top, bot = first, last
    elif ex_last and not ex_first:
        top, bot = last, first
    elif ex_first and ex_last:
        rf = max([x[1]["r"] for x in ex_first])
        rl = max([x[1]["r"] for x in ex_last])
        if TOP_COLLISION_RULE == "first":
            top, bot = first, last
        elif TOP_COLLISION_RULE == "last":
            top, bot = last, first
        else:
            top, bot = (first, last) if rf >= rl else (last, first)
        print("  [!] screw %d: BOTH ends have an extra concentric edge (end at %s: r=%.3f | "
              "end at %s: r=%.3f) -> top = end at %s (rule '%s'). Check it, or set "
              "TOP_END_OVERRIDE = {%d: \"first\" or \"last\"}"
              % (sn, pos_text(first["p"]), rf, pos_text(last["p"]), rl, pos_text(top["p"]),
                 TOP_COLLISION_RULE, sn))
    else:
        mf = max([e["r"] for d, e in near_edges(first["p"], END_TOL_MM)] or [0])
        ml = max([e["r"] for d, e in near_edges(last["p"], END_TOL_MM)] or [0])
        top, bot = (first, last) if mf >= ml else (last, first)
        no_extra_anywhere = True
    mids = [n for n in nl if n is not top and n is not bot]
    roles.append((top, bot, mids))

    extras = ex_first if top is first else ex_last
    if not extras:
        if no_extra_anywhere:
            reason = "no extra concentric edge larger than the hole at either end"
        else:
            reason = "no extra concentric edge larger than the hole at the chosen top end"
        unmatched.append((si, "TOP", top["p"], reason, top))
        continue
    cands = [x for x in extras if x[1]["id"] not in used]
    if not cands:
        unmatched.append((si, "TOP", top["p"], "extra edges already used by another contact", top))
        continue

    chosen = None
    if sn in TOP_EDGE_OVERRIDE:
        for x in cands:
            if TOP_EDGE_OVERRIDE[sn] in x[1]["ids"]:
                chosen = x
        if chosen is None:
            print("  [!] screw %d: TOP_EDGE_OVERRIDE edge not among the extra edges, using rule" % sn)
    elif sn in TOP_RADIUS_OVERRIDE:
        hit = [x for x in cands if abs(x[1]["r"] - TOP_RADIUS_OVERRIDE[sn]) < 0.01]
        if hit:
            chosen = sorted(hit, key=lambda x: x[0])[0]
        else:
            print("  [!] screw %d: no extra edge with radius %.3f, using rule" % (sn, TOP_RADIUS_OVERRIDE[sn]))
    if chosen is None:
        if TOP_RULE == "largest":
            chosen = sorted(cands, key=lambda x: (-x[1]["r"], x[0]))[0]
        else:
            chosen = sorted(cands, key=lambda x: (x[1]["r"], x[0]))[0]

    if len(cands) > 1:
        lst = ", ".join(["r=%.3f(d=%.2f,id=%s)" % (x[1]["r"], x[0], eid_text(x[1]))
                         for x in sorted(cands, key=lambda x: x[1]["r"])])
        print("  screw %d: hole r=%.3f | chosen r=%.3f | extra edges: %s"
              % (sn, chosen[2]["r"], chosen[1]["r"], lst))

    d, e, h = chosen
    used.add(e["id"])
    matches.append((si, "TOP", top, e, d))

# ---------- 2) middle + bottom nodes: hole edge (smallest concentric circle) per body ----------
pairs = []
for si, (top, bot, mids) in enumerate(roles):
    sn = si + 1
    for ni, n in enumerate(mids):
        lab = "MID%d" % (ni + 1)
        lim = MID_LIMIT_OVERRIDE.get((sn, lab), MAX_EDGES_MID)
        for cl in body_clusters(n["p"], MID_TOL_MM):
            d, e = cl["edges"][0]
            pairs.append((d, si, lab, n, e, lim))
    for cl in body_clusters(bot["p"], END_TOL_MM):
        d, e = cl["edges"][0]
        pairs.append((d, si, "BOTTOM", bot, e, 1))
pairs.sort(key=lambda x: (round(x[0], 3), x[4]["r"], x[4]["id"]))

count = {}
for d, si, label, n, e, limit in pairs:
    nk = (si, label)
    if e["id"] in used:
        continue
    if count.get(nk, 0) >= limit:
        continue
    used.add(e["id"])
    count[nk] = count.get(nk, 0) + 1
    matches.append((si, label, n, e, d))

for si, (top, bot, mids) in enumerate(roles):
    if count.get((si, "BOTTOM"), 0) == 0:
        unmatched.append((si, "BOTTOM", bot["p"], "no circular edge within tolerance", bot))
    for ni, n in enumerate(mids):
        if count.get((si, "MID%d" % (ni + 1)), 0) == 0:
            unmatched.append((si, "MID%d" % (ni + 1), n["p"], "no circular edge within tolerance", n))
phase("match nodes to edges")

# ---------- report ----------
print("--- screw numbering: new name <- original geometry tree name ---")
names_seen = {}
for si, (top, bot, mids) in enumerate(roles):
    bl = screw_bodies_tree_order(si)
    allnames = [body_label(b) for b in bl]
    p = screw_list[si][0]["p"]
    names_seen.setdefault(screw_tag(si), []).append(si + 1)
    print("  %s <- tree pos %d '%s' | bodies: %s | first node (%.1f, %.1f, %.1f) mm"
          % (screw_name(si), body_rank(bl[0]) + 1 if body_rank(bl[0]) < 1000000 else -1,
             screw_tag(si), ", ".join(allnames), p[0], p[1], p[2]))
for nm, lst in names_seen.items():
    if len(lst) > 1:
        print("  [i] original tree name '%s' is shared by screws %s" % (nm, lst))

n_split_matches = len([m for m in matches if m[3]["split"]])
print("Matches: %d (on edges made of arcs: %d) | nodes without edge: %d (listed in the summary)"
      % (len(matches), n_split_matches, len(unmatched)))
if VERBOSE_MATCHES:
    for m in matches:
        print("  %s %-7s edge %s%s  r=%.3f mm  dist=%.3f mm  pinball=%.3f mm"
              % (screw_name(m[0]), m[1], eid_text(m[3]), " (arcs)" if m[3]["split"] else "",
                 m[3]["r"], m[4], m[3]["r"] + PINBALL_ADD_MM))
elif n_split_matches:
    print("--- matches on edges made of several arcs ---")
    for m in matches:
        if m[3]["split"]:
            print("  %s %-7s edges %s (%d arcs, %.0f %% of circle)  r=%.3f mm  dist=%.3f mm  "
                  "pinball=%.3f mm"
                  % (screw_name(m[0]), m[1], eid_text(m[3]), m[3]["narcs"], 100.0 * m[3]["cov"],
                     m[3]["r"], m[4], m[3]["r"] + PINBALL_ADD_MM))

tcount = {}
for m in matches:
    tcount[(m[0], m[1])] = tcount.get((m[0], m[1]), 0) + 1
print("--- contacts per screw (automatic) ---")
for si, (top, bot, mids) in enumerate(roles):
    parts = ["TOP=%d" % tcount.get((si, "TOP"), 0)]
    for ni in range(len(mids)):
        parts.append("MID%d=%d" % (ni + 1, tcount.get((si, "MID%d" % (ni + 1)), 0)))
    parts.append("BOTTOM=%d" % tcount.get((si, "BOTTOM"), 0))
    total = sum([v for k, v in tcount.items() if k[0] == si])
    print("  %s: %s  -> total %d" % (screw_name(si), "  ".join(parts), total))

# ---------- transaction helpers (speed) ----------
try:
    Transaction
    HAS_TX = True
except NameError:
    HAS_TX = False
if USE_TRANSACTION and not HAS_TX:
    print("NOTE: Transaction is not available in this Mechanical version -> running without it")

def tx_begin():
    if not (USE_TRANSACTION and HAS_TX):
        return None
    try:
        t = Transaction()
        t.__enter__()
        return t
    except Exception as ex:
        print("  [!] could not start a transaction (%s) - continuing without" % ex)
        return None

def tx_end(t):
    if t is not None:
        try:
            t.__exit__(None, None, None)
        except Exception as ex:
            print("  [!] could not close the transaction (%s)" % ex)

# ---------- rename screws in the geometry tree ----------
def screws_to_process():
    return [si for si in range(len(screw_list))
            if (not PILOT_SCREWS) or ((si + 1) in PILOT_SCREWS)]

def rename_screws_in_tree():
    renamed = 0
    already = 0
    failed_r = []
    if not tree_by_id:
        print("  [!] no tree bodies could be linked to the geometry - screws not renamed")
        return
    tx = tx_begin()
    try:
        for si in screws_to_process():
            bl = screw_bodies_ordered(si)
            for k, b in enumerate(bl):
                nm = screw_name(si)
                if SCREW_SEGMENT_SUFFIX and len(bl) > 1:
                    nm = "%s-Seg%d" % (nm, k + 1)
                obj = tree_by_id.get(wire_bodies[b]["id"])
                old = wire_bodies[b]["name"]
                if DRY_RUN:
                    if obj is not None and old == nm:
                        already += 1
                    else:
                        print("  [dry] would rename '%s' -> '%s'" % (old, nm))
                    continue
                if obj is None:
                    failed_r.append((old, nm, "body not found in tree"))
                    continue
                try:
                    if obj.Name != nm:
                        obj.Name = nm
                        renamed += 1
                    else:
                        already += 1
                except Exception as ex:
                    failed_r.append((old, nm, str(ex)))
    finally:
        tx_end(tx)
    print("Renamed bodies in tree: %d (already correctly named: %d)" % (renamed, already))
    for f in failed_r:
        print("   RENAME FAILED '%s' -> '%s' : %s" % f)

if RENAME_SCREWS_IN_TREE:
    print("--- renaming screws in the geometry tree ---")
    rename_screws_in_tree()
phase("rename screws in the tree")

# ---------- contact helpers ----------
enum_cache = {}   # prop -> (value or None, message or None); looked up once per property

def enum_value(obj, prop, keywords):
    """Find the enum value by keywords once (reflection), then reuse it."""
    if prop in enum_cache:
        return enum_cache[prop]
    res = (None, "%s: not resolved" % prop)
    try:
        ptype = obj.GetType().GetProperty(prop).PropertyType
        names = list(System.Enum.GetNames(ptype))
        res = (None, "%s: no member matching %s. Available: %s" % (prop, keywords, names))
        for nm in names:
            if all([k.lower() in nm.lower() for k in keywords]):
                res = (System.Enum.Parse(ptype, nm), None)
                break
    except Exception as ex:
        res = (None, "%s: %s" % (prop, ex))
    enum_cache[prop] = res
    return res

def set_if_diff(obj, prop, value):
    """Write the property only when it differs from the current value (saves tree updates)."""
    try:
        if getattr(obj, prop) == value:
            return
    except:
        pass
    setattr(obj, prop, value)

def scope(ids):
    s = ExtAPI.SelectionManager.CreateSelectionInfo(SelectionTypeEnum.GeometryEntities)
    s.Ids = list(ids)
    return s

def label_camel(label):
    # TOP -> Top, MID1 -> Mid1, BOTTOM -> Bottom
    return label[0].upper() + label[1:].lower()

def role_order(label):
    # creation order inside one screw: TOP, MID1, MID2, ..., BOTTOM
    if label == "TOP":
        return 0
    if label == "BOTTOM":
        return 10000
    try:
        return int(label[3:])
    except:
        return 5000

def make_contact_name(si, label, edge_id):
    parts = [screw_name(si)]
    if USE_TAG:
        parts.append(contact_tag(si))
    parts.append("%sEdge-%d" % (label_camel(label), edge_id))
    return NAME_SEPARATOR.join(parts)

def norm_name(s):
    return "".join([ch for ch in str(s).lower() if ch.isalnum()])

def find_groups(name):
    """Connection groups whose name matches, ignoring case, spaces, '_' and '-'."""
    found = []
    try:
        kids = list(model.Connections.Children)
    except Exception as ex:
        print("  [!] could not read the Connections branch (%s)" % ex)
        return found
    want = norm_name(name)
    for ch in kids:
        try:
            if norm_name(ch.Name) == want:
                found.append(ch)
        except:
            pass
    if not found:
        print("  no group matches '%s'. Objects under Connections:" % name)
        for ch in kids:
            try:
                print("     '%s' (%s)" % (ch.Name, ch.GetType().Name))
            except:
                pass
    return found

def collect_contacts(node, depth=0):
    """All contact regions below node, including those inside (manually made) folders."""
    out = []
    if depth > 12:
        return out
    try:
        kids = list(node.Children)
    except:
        return out
    for ch in kids:
        try:
            is_contact = hasattr(ch, "ContactType")
        except:
            is_contact = False
        if is_contact:
            out.append(ch)
        else:
            out.extend(collect_contacts(ch, depth + 1))
    return out

def sel_ids(sel):
    try:
        return set([int(i) for i in sel.Ids])
    except:
        return None

def assign_scopes(c, node_vids, edge_ids):
    """Ansys 2019 R2: the NODE (contact side) must be selected FIRST, then the edge(s)
    (target side). Otherwise the pinball center ends up on the edge and the contact is open."""
    c.SourceLocation = scope(node_vids)     # 1) node (vertex of the beam)
    c.TargetLocation = scope(edge_ids)      # 2) edge(s) - all arcs of a split hole edge

def check_scopes(c, node_vids, edge_ids):
    """True/False = Source is the node and Target is the edge(s); None = could not be read."""
    try:
        src = sel_ids(c.SourceLocation)
        tgt = sel_ids(c.TargetLocation)
    except:
        return None
    if src is None or tgt is None:
        return None
    return src == set([int(v) for v in node_vids]) and tgt == set([int(i) for i in edge_ids])

# ---------- planned contacts ----------
todo = [m for m in matches if (not PILOT_SCREWS) or ((m[0] + 1) in PILOT_SCREWS)]
# screw by screw, then role order, then edge id (stable for two edges at one node)
todo.sort(key=lambda m: (m[0], role_order(m[1]), m[3]["id"]))
planned_names = set([make_contact_name(si, label, e["id"]) for (si, label, n, e, d) in todo])

# ---------- existing contacts in the group (re-run support) ----------
print("--- existing contacts in group '%s' ---" % GROUP_NAME)
groups_found = find_groups(GROUP_NAME)
group = groups_found[0] if groups_found else None
if len(groups_found) > 1:
    print("  [!] %d groups named '%s' found -> using the first one" % (len(groups_found), GROUP_NAME))

scan_group = group is not None
if group is not None and REBUILD_FROM_SCRATCH:
    if DRY_RUN:
        print("  REBUILD_FROM_SCRATCH: the group WOULD be deleted (DRY_RUN) - existing contacts ignored")
        scan_group = False
    else:
        try:
            group.Delete()
            group = None
            scan_group = False
            print("  REBUILD_FROM_SCRATCH: deleted group '%s' with all folders and contacts" % GROUP_NAME)
        except Exception as ex:
            print("  [!] could not delete the group (%s) - existing contacts are kept and scanned" % ex)

existing_list = []     # (contact, name, source ids or None, target ids or None)
n_scope_try = 0
n_scope_ok = 0
scan_ok = True
if group is not None and scan_group:
    try:
        n_children = len(list(group.Children))
    except:
        n_children = 0
    for c in collect_contacts(group):
        try:
            nm = str(c.Name)
        except:
            nm = ""
        src = None
        tgt = None
        if CHECK_EXISTING_BY_SCOPE and not (FAST_EXISTING_SCAN and nm in planned_names):
            n_scope_try += 1
            try:
                src = sel_ids(c.SourceLocation)
                tgt = sel_ids(c.TargetLocation)
            except:
                src = None
                tgt = None
            if src and tgt:
                n_scope_ok += 1
        existing_list.append((c, nm, src, tgt))
    if n_children > 0 and not existing_list:
        scan_ok = False
        print("  [!] the group has %d child objects but no contacts could be read -> creation is "
              "SKIPPED to avoid duplicates. Send me this message." % n_children)
    if CHECK_EXISTING_BY_SCOPE and n_scope_try > 0 and n_scope_ok == 0:
        scan_ok = False
        print("  [!] the scope of the existing contacts cannot be read -> creation is SKIPPED to "
              "avoid duplicates. Set CHECK_EXISTING_BY_SCOPE = False to use names only (contacts "
              "with old-style names are then not recognised).")
elif group is None:
    print("  group '%s' does not exist yet -> it will be created" % GROUP_NAME)

ex_names = set([x[1] for x in existing_list])
ex_by_vertex = {}      # vertex id -> list of target id sets
for c, nm, src, tgt in existing_list:
    if src and tgt:
        for v in src:
            ex_by_vertex.setdefault(v, []).append(tgt)

def planned_exists(cname, vids, eids):
    if cname in ex_names:
        return True
    if CHECK_EXISTING_BY_SCOPE:
        es = set(eids)
        for v in vids:
            for tgt in ex_by_vertex.get(v, []):
                if tgt & es:
                    return True
    return False

def node_has_contact(node):
    for v in node["vids"]:
        if v in ex_by_vertex:
            return True
    return False

todo_new = []          # (si, label, node, edge, dist, contact name)
n_exist = 0
for (si, label, n, e, d) in todo:
    cname = make_contact_name(si, label, e["id"])
    if planned_exists(cname, n["vids"], e["ids"]):
        n_exist += 1
    else:
        todo_new.append((si, label, n, e, d, cname))

# contacts that use a node of this script with an edge the script does not select
planned_by_vertex = {}     # vertex id -> set of expected edge ids
for (si, label, n, e, d) in todo:
    for v in n["vids"]:
        planned_by_vertex.setdefault(v, set()).update(e["ids"])
conflicts = []             # (contact, name)
for c, nm, src, tgt in existing_list:
    if not src or not tgt:
        continue
    for v in src:
        exp = planned_by_vertex.get(v)
        if exp is not None and not (tgt & exp):
            conflicts.append((c, nm))
            break

n_name_known = len([x for x in existing_list if x[1] in planned_names])
print("Existing contacts found: %d (recognised by planned name: %d, scope read: %d of %d) | "
      "planned: %d | already existing: %d | to create: %d"
      % (len(existing_list), n_name_known, n_scope_ok, n_scope_try, len(todo), n_exist, len(todo_new)))
if conflicts:
    print("--- [?] %d existing contact(s) use a node of this script but an edge the script does "
          "NOT select (wrong edge from an earlier run, or a manual contact) ---" % len(conflicts))
    for c, nm in conflicts[:LIST_NEW_MAX]:
        print("   '%s'" % nm)
    if len(conflicts) > LIST_NEW_MAX:
        print("   ... and %d more" % (len(conflicts) - LIST_NEW_MAX))
    if DELETE_CONFLICTING_CONTACTS and not DRY_RUN:
        print("   DELETE_CONFLICTING_CONTACTS = True -> these contacts will be deleted")
    else:
        print("   They are NOT deleted. Remove wrong ones by hand, or set "
              "DELETE_CONFLICTING_CONTACTS = True after reviewing this list.")
phase("scan existing contacts")

# ---------- create missing contacts ----------
created = 0
deleted = 0
failed = []          # (name, reason)
prop_warnings = {}   # message -> count
scope_bad = []       # names of contacts whose read-back scope differs from the plan
scope_unread = 0     # contacts whose scope could not be read back
new_names = []
t_start = time.time()
t_create = t_start
t_end = t_start

if not DRY_RUN:
    if not scan_ok:
        print("Creation skipped (see the message above).")
    else:
        if DELETE_CONFLICTING_CONTACTS and conflicts:
            for c, nm in conflicts:
                try:
                    c.Delete()
                    deleted += 1
                except Exception as ex:
                    print("  [!] could not delete '%s' (%s)" % (nm, ex))
        if todo_new:
            if group is None:
                group = model.Connections.AddConnectionGroup()
                group.Name = GROUP_NAME
            n_screws = len(set([m[0] for m in todo_new]))
            cur_si = None
            done_screws = 0
            t_create = time.time()
            tx = tx_begin()
            try:
                for (si, label, n, e, d, cname) in todo_new:
                    if si != cur_si:
                        cur_si = si
                        done_screws += 1
                        if TX_BATCH_SCREWS and done_screws > 1 and (done_screws - 1) % TX_BATCH_SCREWS == 0:
                            tx_end(tx)
                            tx = tx_begin()
                        if PROGRESS_EVERY and done_screws % PROGRESS_EVERY == 0:
                            msg = "  ... %d of %d screws done (%d contacts)" % (done_screws, n_screws, created)
                            if SHOW_TIMING and created > 0:
                                el = time.time() - t_create
                                per = el / created
                                left = per * (len(todo_new) - created)
                                msg += " | elapsed %.0f s, %.2f s/contact, about %.0f s left" % (el, per, left)
                            print(msg)
                    c = None
                    try:
                        c = group.AddContactRegion()
                        c.Name = cname
                        if not FAST_PROPERTY_ORDER:
                            assign_scopes(c, n["vids"], e["ids"])   # node first, then edge(s)
                        set_if_diff(c, "ContactType", ContactType.Bonded)
                        set_if_diff(c, "ContactFormulation", ContactFormulation.MPC)
                        set_if_diff(c, "PinballRegion", ContactPinballType.Radius)
                        c.PinballRadius = Quantity("%.4f [mm]" % (e["r"] + PINBALL_ADD_MM))
                        for prop, kws in (("ConstraintType", ("distributed", "inside")),
                                          ("TrimContact", ("program",))):
                            val, msg = enum_value(c, prop, kws)
                            if val is None:
                                prop_warnings[msg] = prop_warnings.get(msg, 0) + 1
                            else:
                                set_if_diff(c, prop, val)
                        if FAST_PROPERTY_ORDER:
                            assign_scopes(c, n["vids"], e["ids"])   # node first, then edge(s)
                        created += 1
                        new_names.append(cname)
                        if VERIFY_SCOPE_AFTER_CREATE:
                            ok = check_scopes(c, n["vids"], e["ids"])
                            if ok is False:
                                scope_bad.append(cname)
                            elif ok is None:
                                scope_unread += 1
                    except Exception as ex:
                        failed.append((cname, str(ex)))
                        try:                      # remove the half-made contact
                            if c is not None:
                                c.Delete()
                        except:
                            pass
            finally:
                tx_end(tx)
            t_end = time.time()
phase("create contacts")

# ---------- final summary ----------
print("")
print("================ SUMMARY ================")
if DRY_RUN:
    print("DRY_RUN = True -> NOTHING WAS CHANGED. Set DRY_RUN = False at the top and run again.")
    print("Would create     : %d contacts (already existing: %d)" % (len(todo_new), n_exist))
else:
    print("Connection group : '%s'" % GROUP_NAME)
    print("Planned contacts : %d | already existing (kept): %d | to create: %d"
          % (len(todo), n_exist, len(todo_new)))
    print("Contacts created : %d (targets made of several arcs: %d)"
          % (created, len([m for m in todo_new if m[3]["split"]])))
    print("Failed contacts  : %d" % len(failed))
    for f in failed:
        print("   FAILED %s -> %s" % (f[0], f[1]))
    for msg, cnt in prop_warnings.items():
        print("   PROPERTY NOT SET (%d contacts): %s" % (cnt, msg))
    if VERIFY_SCOPE_AFTER_CREATE and created > 0:
        print("Scope check      : %d of %d new contacts verified (Source = node, Target = edge(s))"
              % (created - len(scope_bad) - scope_unread, created))
        for nm in scope_bad[:LIST_NEW_MAX]:
            print("   SCOPE MISMATCH %s -> check this contact (pinball center / open contact)" % nm)
        if scope_unread:
            print("   scope could not be read back for %d contacts" % scope_unread)
    if deleted:
        print("Conflicting contacts deleted: %d" % deleted)
    if SHOW_TIMING and created > 0:
        print("Creation time    : %.1f s total, %.2f s per contact (whole run %.1f s)"
              % (t_end - t_create, (t_end - t_create) / created, t_end - t_start))
    if LIST_NEW_CONTACTS and new_names:
        print("New contacts (added at the end of the group - move them into your folders if needed):")
        for nm in new_names[:LIST_NEW_MAX]:
            print("   %s" % nm)
        if len(new_names) > LIST_NEW_MAX:
            print("   ... and %d more" % (len(new_names) - LIST_NEW_MAX))
print("Rejected arc groups (not used as hole edges): %d" % len(rejected_groups))
print("Existing contacts needing a decision [?]: %d" % len(conflicts))
n_missing = 0
print("Nodes WITHOUT edge, create these MANUALLY:")
for u in unmatched:
    has = node_has_contact(u[4])
    if not has:
        n_missing += 1
    tol = END_TOL_MM if u[1] in ("TOP", "BOTTOM") else MID_TOL_MM
    hint = single_hint(u[2], tol)
    print("   %s %s at (%.2f, %.2f, %.2f) mm - %s%s  %s"
          % (screw_name(u[0]), u[1], u[2][0], u[2][1], u[2][2], u[3],
             (" | nearby single arc: " + hint) if hint else "",
             "[contact already present in the group]" if has else "[MISSING]"))
print("Nodes still missing a contact: %d of %d" % (n_missing, len(unmatched)))
if SHOW_PHASE_TIMES:
    print("--- time per phase ---")
    for nm, sec in phase_times:
        print("   %-40s %8.1f s" % (nm, sec))
    print("   %-40s %8.1f s" % ("TOTAL", time.time() - T_SCRIPT_START))
print("=========================================")
