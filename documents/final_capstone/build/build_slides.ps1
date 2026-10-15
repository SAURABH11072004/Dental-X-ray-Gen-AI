# Builds (1) DentaMind_AI_Research_Diagrams.pptx - four editable diagrams (native shapes + glued connectors), each slide
# exported as PNG for the report - and (2) DentaMind_AI_Capstone_Presentation.pptx (+ PDF) from slides.json.
# Uses PowerPoint COM only (no downloads). Run:  powershell -NoProfile -File documents\final_capstone\build\build_slides.ps1
$ErrorActionPreference = "Stop"
$Base  = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)   # documents\final_capstone
$Root  = Split-Path -Parent (Split-Path -Parent $Base)                           # project root
$Fig   = Join-Path $Base "figures"
# slides_resolved.json = slides.json with [@key] citations replaced by the report's IEEE numbers (written by build_report.py)
$specFile = Join-Path $PSScriptRoot "slides_resolved.json"
if (-not (Test-Path $specFile)) { $specFile = Join-Path $PSScriptRoot "slides.json" }
$Spec  = Get-Content $specFile -Raw -Encoding UTF8 | ConvertFrom-Json

# ---------- unicode helpers (keep this file ASCII) ----------
$GE = [string][char]0x2265; $AR = [string][char]0x2192; $MD = [string][char]0x00B7; $ND = [string][char]0x2013; $PM = [string][char]0x00B1
function C([int]$r, [int]$g, [int]$b) { return $r + 256 * $g + 65536 * $b }
$INK = C 26 26 26; $GREY = C 90 90 90; $LINE = C 64 64 64; $MODEL = C 226 226 226; $WHITE = C 255 255 255; $PALE = C 245 245 245
$NAVY = C 31 58 95; $TEAL = C 15 118 110; $MUTED = C 85 101 122; $AMBER = C 180 83 9

# ---------- drawing context: a 960 x 460 virtual canvas mapped onto a slide region ----------
$script:S = 1.0; $script:OX = 0; $script:OY = 0; $script:SL = $null; $script:FONT = "Calibri"; $script:FSC = 1.0   # FSC: font scale used while drawing diagrams
function Ctx($slide, [double]$ox, [double]$oy, [double]$scale) { $script:SL = $slide; $script:OX = $ox; $script:OY = $oy; $script:S = $scale }
function X([double]$v) { return $script:OX + $v * $script:S }
function Y([double]$v) { return $script:OY + $v * $script:S }
function D([double]$v) { return $v * $script:S }

function StyleText($shp, [double]$size, [int]$color, [bool]$bold = $false, [int]$align = 2) {
    $tf = $shp.TextFrame; $tf.WordWrap = -1; $tf.AutoSize = 0
    $tf.MarginLeft = D 5; $tf.MarginRight = D 5; $tf.MarginTop = D 3; $tf.MarginBottom = D 3
    $tf.VerticalAnchor = 3   # middle
    $r = $tf.TextRange; $r.Font.Name = $script:FONT; $r.Font.Size = [math]::Round((D $size) * $script:FSC * 2) / 2; $r.Font.Color.RGB = $color; $r.Font.Bold = [int]$bold
    $r.ParagraphFormat.Alignment = $align
}
# Box: kind = plain | model | note | label | data
function Box([double]$x, [double]$y, [double]$w, [double]$h, [string]$text, [string]$kind = "plain", [double]$size = 11) {
    $shapeType = 5   # rounded rectangle
    if ($kind -eq "data") { $shapeType = 86 }         # flowchart magnetic disk (data store); sites 1 top, 2 left, 3 bottom, 4 right
    if ($kind -eq "label") { $shapeType = 1 }
    $s = $script:SL.Shapes.AddShape($shapeType, (X $x), (Y $y), (D $w), (D $h))
    if ($shapeType -eq 5) { $s.Adjustments.Item(1) = 0.12 }
    $s.Fill.Solid(); $s.Fill.ForeColor.RGB = $WHITE
    $s.Line.ForeColor.RGB = $LINE; $s.Line.Weight = [math]::Max(0.75, (D 1.1))
    if ($kind -eq "model") { $s.Fill.ForeColor.RGB = $MODEL }
    if ($kind -eq "data")  { $s.Fill.ForeColor.RGB = $PALE }
    if ($kind -eq "note")  { $s.Line.DashStyle = 4; $s.Fill.ForeColor.RGB = $WHITE }
    if ($kind -eq "label") { $s.Fill.Visible = 0; $s.Line.Visible = 0 }
    $s.Shadow.Visible = 0
    $s.TextFrame.TextRange.Text = $text
    $bold = $false; $align = 2
    if ($kind -eq "label") { $bold = $true; $align = 1 }
    StyleText $s $size $INK $bold $align
    if ($kind -ne "label" -and $text.Contains("`r")) {
        # first line bold = the component's name; following lines = detail
        $s.TextFrame.TextRange.Paragraphs(1).Font.Bold = -1
        $n = $s.TextFrame.TextRange.Paragraphs().Count
        for ($i = 2; $i -le $n; $i++) { $p = $s.TextFrame.TextRange.Paragraphs($i); $p.Font.Size = [math]::Round((D ($size - 1.5)) * $script:FSC * 2) / 2; $p.Font.Color.RGB = $GREY }
    }
    return $s
}
function Diamond([double]$x, [double]$y, [double]$w, [double]$h, [string]$text, [double]$size = 10) {
    $s = $script:SL.Shapes.AddShape(4, (X $x), (Y $y), (D $w), (D $h))
    $s.Fill.Solid(); $s.Fill.ForeColor.RGB = $WHITE; $s.Line.ForeColor.RGB = $LINE; $s.Line.Weight = [math]::Max(0.75, (D 1.1)); $s.Shadow.Visible = 0
    $s.TextFrame.TextRange.Text = $text; StyleText $s $size $INK $true 2
    return $s
}
function Container([double]$x, [double]$y, [double]$w, [double]$h, [string]$title) {
    $s = $script:SL.Shapes.AddShape(1, (X $x), (Y $y), (D $w), (D $h))
    $s.Fill.Visible = 0; $s.Line.ForeColor.RGB = (C 150 150 150); $s.Line.DashStyle = 4; $s.Line.Weight = [math]::Max(0.5, (D 0.9)); $s.Shadow.Visible = 0
    $s.TextFrame.TextRange.Text = $title; StyleText $s 9.5 $GREY $true 1
    $s.TextFrame.VerticalAnchor = 1; $s.TextFrame.MarginTop = D 2; $s.TextFrame.MarginLeft = D 6
    return $s
}
# glued connector; sites for rectangles/rounded rectangles: 1 top, 2 left, 3 bottom, 4 right
function Link($a, [int]$sa, $b, [int]$sb, [int]$type = 1, [string]$label = "", [bool]$dashed = $false) {
    # the magnetic-disk shape (86) has 5 sites: 1 inner top, 2 top, 3 left, 4 bottom, 5 right -> shift logical sites by one
    if ($a.AutoShapeType -eq 86) { $sa = $sa + 1 }
    if ($b.AutoShapeType -eq 86) { $sb = $sb + 1 }
    $c = $script:SL.Shapes.AddConnector($type, 0, 0, 10, 10)
    $c.ConnectorFormat.BeginConnect($a, $sa); $c.ConnectorFormat.EndConnect($b, $sb)
    $c.Line.ForeColor.RGB = $LINE; $c.Line.Weight = [math]::Max(0.75, (D 1.25)); $c.Line.EndArrowheadStyle = 2
    $c.Line.EndArrowheadLength = 2; $c.Line.EndArrowheadWidth = 2
    if ($dashed) { $c.Line.DashStyle = 4 }
    return $c
}
function Txt([double]$x, [double]$y, [double]$w, [double]$h, [string]$text, [double]$size = 10, [int]$color = $GREY, [bool]$bold = $false, [int]$align = 1) {
    $t = $script:SL.Shapes.AddTextbox(1, (X $x), (Y $y), (D $w), (D $h))
    $t.TextFrame.TextRange.Text = $text; StyleText $t $size $color $bold $align; $t.TextFrame.VerticalAnchor = 1
    return $t
}
$N = "`r"   # paragraph break inside a shape

# ======================= the four diagrams (960 x 460 canvas) =======================
function Draw-Architecture {
    foreach ($row in @(@(15, "Client (browser)"), @(98, ("Transport &" + $N + "API gateway")), @(180, ("Application" + $N + "services")), @(295, ("ML core" + $N + "(PyTorch)")))) {
        Box 0 $row[0] 120 60 $row[1] "label" 11 | Out-Null
    }
    $w3 = 180; $g3 = 22; $x0 = 130
    $c1 = Box $x0 15 $w3 60 ("X-ray Analysis page" + $N + "upload or pick image, viewer, regions") "plain"
    $c2 = Box ($x0 + $w3 + $g3) 15 $w3 60 ("Reports page" + $N + "draft report, EN / HI / MR") "plain"
    $c3 = Box ($x0 + 2 * ($w3 + $g3)) 15 $w3 60 ("Review Findings page" + $N + "decisions and approvals") "plain"
    $gw = Box $x0 103 (3 * $w3 + 2 * $g3) 50 ("React 18 + Vite proxy  $AR  FastAPI on 127.0.0.1:8000" + $N + "API token added server-side $MD token auth $MD rate limits $MD input validation") "plain"
    $s1 = Box $x0 180 $w3 60 ("Analysis pipeline service" + $N + "runs the four models, flags") "plain"
    $s2 = Box ($x0 + $w3 + $g3) 180 $w3 60 ("Report service" + $N + "template draft + output validator") "plain"
    $s3 = Box ($x0 + 2 * ($w3 + $g3)) 180 $w3 60 ("Review & registry services" + $N + "revisions, promotion, ledger") "plain"
    $ml = Container $x0 262 (3 * $w3 + 2 * $g3) 112 "dentexmodel package"
    $mw = 106; $mg = 9; $mx = $x0 + 9
    $m = @()
    $labels = @(("Detection" + $N + "Faster R-CNN"), ("Numbering" + $N + "Faster R-CNN, 32 FDI"), ("Segmentation" + $N + "Mask R-CNN"), ("Classifier" + $N + "ResNet-50, 4 cls"), ("Uncertainty" + $N + "flip-TTA, entropy"))
    for ($i = 0; $i -lt 5; $i++) { $kind = "model"; if ($i -eq 4) { $kind = "plain" }; $m += Box ($mx + $i * ($mw + $mg)) 292 $mw 66 $labels[$i] $kind 10.5 }
    Link $c1 3 $gw 1 2 | Out-Null; Link $c2 3 $gw 1 | Out-Null; Link $c3 3 $gw 1 2 | Out-Null
    Link $gw 3 $s1 1 2 | Out-Null; Link $gw 3 $s2 1 | Out-Null; Link $gw 3 $s3 1 2 | Out-Null
    Link $s1 3 $ml 1 2 | Out-Null
    $st = Container 775 15 185 360 "Storage (local disk)"
    $d1 = Box 790 45 155 62 ("SQLite database" + $N + "analyses, reports, reviews") "data" 10.5
    $d2 = Box 790 125 155 62 ("Checkpoints" + $N + "4 models + sidecars, SHA-256") "data" 10.5
    $d3 = Box 790 205 155 62 ("DENTEX images" + $N + "manifest + split file") "data" 10.5
    $d4 = Box 790 285 155 62 ("Evaluation reports" + $N + "JSON / MD + test ledger") "data" 10.5
    Link $s3 4 $d1 2 2 | Out-Null
    Link $ml 4 $d2 2 2 | Out-Null
    Txt 0 395 960 60 ("Grey boxes are trained networks; white boxes are ordinary code. Everything runs on one machine and the API listens only on the loopback address. An optional OpenAI-compatible LLM path for report wording exists in code but is not configured, so all drafts in this project come from the deterministic template.") 10 $GREY $false 1 | Out-Null
}

function Draw-Inference {
    $w = 140; $g = 22; $y1 = 30; $y2 = 215; $h = 92
    $top = @(
        ("1  Input radiograph" + $N + "upload or test image (PNG/JPEG)"),
        ("2  Pre-processing" + $N + "load grayscale $AR 3-channel tensor"),
        ("3  Tooth detection" + $N + "Faster R-CNN, score $GE 0.3"),
        ("4  FDI numbering" + $N + "Faster R-CNN, matched at IoU $GE 0.5"),
        ("5  Tooth segmentation" + $N + "Mask R-CNN outline per tooth"),
        ("6  Tooth crops" + $N + "box + 10 % padding, 224 px, ImageNet norm."))
    $kinds = @("plain", "plain", "model", "model", "model", "plain")
    $A = @()
    for ($i = 0; $i -lt 6; $i++) { $A += Box (6 + $i * ($w + $g)) $y1 $w $h $top[$i] $kinds[$i] 11 }
    for ($i = 0; $i -lt 5; $i++) { Link $A[$i] 4 $A[$i + 1] 2 | Out-Null }
    $bot = @(
        ("7  Finding classifier" + $N + "ResNet-50, 4 classes, argmax"),
        ("8  Uncertainty" + $N + "flip-TTA disagreement, normalised entropy"),
        ("9  Flags & abstention" + $N + "entropy $GE 0.397 $AR 'no reliable class'"),
        ("10  Draft report" + $N + "evidence $AR template (EN/HI/MR) $AR validator"),
        ("11  Human review" + $N + "confirm / correct / reject"))
    $bk = @("model", "plain", "plain", "plain", "plain")
    $B = @()
    for ($i = 0; $i -lt 5; $i++) { $B += Box (6 + (5 - $i) * ($w + $g)) $y2 $w $h $bot[$i] $bk[$i] 11 }
    Link $A[5] 3 $B[0] 1 | Out-Null
    for ($i = 0; $i -lt 4; $i++) { Link $B[$i] 2 $B[$i + 1] 4 | Out-Null }
    $o = Box 6 $y2 $w $h ("Per-region output" + $N + "box, FDI number, outline, closest class + raw score, flags") "note" 11
    Link $B[4] 2 $o 4 1 "" $true | Out-Null
    Txt 6 335 948 110 ("Order of operations as implemented in backend/services/pipeline.py. Thresholds: detection score 0.3 (boxes below 0.5 are flagged as weak detections); abstention when normalised entropy $GE 0.3966, chosen by Youden's J on the calibration split; flip-instability flag when TTA disagreement $GE 0.0762. The classifier has no healthy class, so every detected tooth receives its closest of four findings; the system therefore presents a candidate for review, never a diagnosis.") 10.5 $GREY $false 1 | Out-Null
}

function Draw-Training {
    $h = 70; $w = 204; $g = 40
    $a1 = Box 10 10 $w $h ("DENTEX archives" + $N + "3,653 PNG files in 5 folders") "data" 11
    $a2 = Box (10 + ($w + $g)) 10 $w $h ("Dataset audit" + $N + "pixel hashing $AR 2,716 unique films") "plain" 11
    $a3 = Box (10 + 2 * ($w + $g)) 10 $w $h ("Duplicate-aware split" + $N + "1,133 annotated radiographs") "plain" 11
    $a4 = Box (10 + 3 * ($w + $g)) 10 $w $h ("Leakage check" + $N + "18 checks: 17 pass, 1 warning") "plain" 11
    Link $a1 4 $a2 2 | Out-Null; Link $a2 4 $a3 2 | Out-Null; Link $a3 4 $a4 2 | Out-Null
    $sw = 200; $sg = 50; $sy = 130
    $tr = Box 10 $sy $sw 56 ("Train split" + $N + "794 radiographs") "data" 11
    $va = Box (10 + ($sw + $sg)) $sy $sw 56 ("Validation split" + $N + "113 radiographs") "data" 11
    $ca = Box (10 + 2 * ($sw + $sg)) $sy $sw 56 ("Calibration split" + $N + "113 radiographs") "data" 11
    $te = Box (10 + 3 * ($sw + $sg)) $sy $sw 56 ("Test split" + $N + "113 radiographs, ledger-gated") "data" 11
    foreach ($s in @($tr, $va, $ca, $te)) { Link $a4 3 $s 1 2 | Out-Null }
    $cy = 240
    $t1 = Box 10 $cy $sw 80 ("Training" + $N + "AdamW, cosine LR, AMP; manifest with data + code hashes") "model" 10.5
    $t2 = Box (10 + ($sw + $sg)) $cy $sw 80 ("Selection & comparison" + $N + "best epoch; 5-seed runs; pre-registered rule") "plain" 10.5
    $t3 = Box (10 + 2 * ($sw + $sg)) $cy $sw 80 ("Uncertainty thresholds" + $N + "Youden's J; temperature fit (not applied)") "plain" 10.5
    $t4 = Box (10 + 3 * ($sw + $sg)) $cy $sw 80 ("Historical test report" + $N + "once per checkpoint, hash-chained ledger") "plain" 10.5
    Link $tr 3 $t1 1 | Out-Null; Link $va 3 $t2 1 | Out-Null; Link $ca 3 $t3 1 | Out-Null; Link $te 3 $t4 1 | Out-Null
    Link $t1 4 $t2 2 | Out-Null
    $p = Box (10 + ($sw + $sg)) 360 (2 * $sw + $sg) 64 ("Promotion gate (human decision)" + $N + "needs a validation report + written justification; recorded with rollback") "plain" 11
    Link $t2 3 $p 1 2 | Out-Null
    $n = Box (10 + 3 * ($sw + $sg)) 360 $sw 64 ("Never used for model selection, thresholds or promotion") "note" 10
    Link $t4 3 $n 1 1 "" $true | Out-Null
    Box 10 360 $sw 64 ("All splits are assigned per unique radiograph, so duplicate files never cross splits.") "note" 10 | Out-Null
}

function Draw-Review {
    $r1 = Box 10 95 175 84 ("AI output per region" + $N + "box, FDI number, closest class + score, flags") "plain" 10.5
    $q  = Diamond 225 82 170 110 ("Any flag?") 11
    $nr = Box 440 18 200 84 ("Needs review" + $N + "abstained, weak detection, unstable, unnumbered") "plain" 10.5
    $nf = Box 440 172 200 84 ("No flag" + $N + "shown in the table, still open to review") "plain" 10.5
    $rv = Box 690 77 260 120 ("Reviewer decision" + $N + "confirm $MD correct class $MD reject $MD set tooth number $MD mark unassigned $MD specialist review $MD unusable image") "plain" 10.5
    Link $r1 4 $q 2 | Out-Null
    Link $q 1 $nr 2 2 | Out-Null
    Link $q 3 $nf 2 2 | Out-Null
    Txt 330 36 50 18 "yes" 10 $GREY $true 1 | Out-Null
    Txt 316 196 50 18 "no" 10 $GREY $true 1 | Out-Null
    Link $nr 4 $rv 2 2 | Out-Null
    Link $nf 4 $rv 2 2 | Out-Null
    $rec = Box 690 228 260 62 ("Review record (SQLite)" + $N + "revisioned; previous output kept; reviewer + self-declared role") "plain" 10.5
    Link $rv 3 $rec 1 | Out-Null
    $ap = Box 690 312 260 62 ("Approval by a second person" + $N + "approved or rejected; identical resubmission refused") "plain" 10.5
    Link $rec 3 $ap 1 | Out-Null
    $rp = Box 370 312 270 62 ("Report draft marked 'reviewed'" + $N + "the clinician stays responsible for any diagnosis") "plain" 10.5
    $el = Box 370 392 270 62 ("Training-eligibility check" + $N + "only unassigned images, never a copy of a labelled film") "plain" 10.5
    Link $ap 2 $rp 4 | Out-Null
    Link $ap 3 $el 4 2 | Out-Null
    $cm = Box 10 392 310 62 ("Candidate model" + $N + "validation report $AR human promotion gate") "model" 10.5
    Link $el 2 $cm 4 | Out-Null
    Txt 10 250 330 110 ("The AI never finalises a finding. Every region stays editable, approvals need a second person, and reviewed images only become training data after the leakage rules are checked.") 10.5 $GREY $false 1 | Out-Null
}

# ======================= PowerPoint session =======================
$app = New-Object -ComObject PowerPoint.Application
try {
    # ---------- (1) diagrams deck ----------
    $dg = $app.Presentations.Add(0)
    $dg.PageSetup.SlideWidth = 980; $dg.PageSetup.SlideHeight = 480
    $names = @("diagram_architecture", "diagram_inference_pipeline", "diagram_training_evaluation", "diagram_human_review")
    $fns = @("Draw-Architecture", "Draw-Inference", "Draw-Training", "Draw-Review")
    for ($i = 0; $i -lt 4; $i++) {
        $sl = $dg.Slides.Add($i + 1, 12)
        Ctx $sl 10 10 1.0
        $script:FSC = 1.2
        & $fns[$i]
        $script:FSC = 1.0
    }
    $dpath = Join-Path $Base "DentaMind_AI_Research_Diagrams.pptx"
    if (Test-Path $dpath) { Remove-Item $dpath }
    $dg.SaveAs($dpath)
    for ($i = 0; $i -lt 4; $i++) { $dg.Slides.Item($i + 1).Export((Join-Path $Fig ($names[$i] + ".png")), "PNG", 2940, 1440) }
    $dg.Close()
    Write-Output "diagrams saved: $dpath"

    # ---------- (2) presentation ----------
    $p = $app.Presentations.Add(0)
    $p.PageSetup.SlideWidth = 960; $p.PageSetup.SlideHeight = 540
    $W = 960; $H = 540
    $total = $Spec.slides.Count
    $idx = 0
    foreach ($sd in $Spec.slides) {
        $idx++
        $sl = $p.Slides.Add($idx, 12)
        $sl.FollowMasterBackground = 0; $sl.Background.Fill.Solid(); $sl.Background.Fill.ForeColor.RGB = $WHITE
        Ctx $sl 0 0 1.0
        if ($sd.type -eq "title") {
            $band = $sl.Shapes.AddShape(1, 0, 0, $W, 300); $band.Fill.Solid(); $band.Fill.ForeColor.RGB = $NAVY; $band.Line.Visible = 0; $band.Shadow.Visible = 0
            $acc = $sl.Shapes.AddShape(1, 60, 286, 120, 5); $acc.Fill.Solid(); $acc.Fill.ForeColor.RGB = (C 45 212 191); $acc.Line.Visible = 0
            $t = Txt 60 64 840 110 $sd.title 38 $WHITE $true 1
            $t2 = Txt 60 186 840 80 $sd.subtitle 18 (C 203 213 225) $false 1
            $m = Txt 60 320 840 200 ($sd.meta -join $N) 14 $INK $false 1
            $m.TextFrame.TextRange.ParagraphFormat.SpaceAfter = 4
        }
        else {
            $t = Txt 40 22 880 50 $sd.title 26 $NAVY $true 1; $t.TextFrame.VerticalAnchor = 3
            $acc = $sl.Shapes.AddShape(1, 42, 74, 70, 3); $acc.Fill.Solid(); $acc.Fill.ForeColor.RGB = $TEAL; $acc.Line.Visible = 0
            $f = Txt 40 512 700 20 ("DentaMind AI $MD B.Tech Capstone $MD PCCOE CSE (AI & ML) 2026-27") 9 $MUTED $false 1
            $pn = Txt 820 512 100 20 ("$idx / $total") 9 $MUTED $false 3
            $L = 42; $T = 92; $BW = 876; $BH = 405
            if ($sd.callout) { $BH = 340 }
            if ($sd.type -eq "diagram") {
                $sc = [math]::Min($BW / 960.0, ($BH + 10) / 460.0)
                Ctx $sl ($L + ($BW - 960 * $sc) / 2) ($T - 4) $sc
                $script:FSC = 1.2
                & ("Draw-" + $sd.diagram)
                $script:FSC = 1.0
                Ctx $sl 0 0 1.0
            }
            # a table always spans the full width at the top; image and bullets share the space below it
            if ($sd.table) {
                $tw = $BW
                $rows = $sd.table.rows.Count + 1; $cols = $sd.table.header.Count
                $rh = 22; if ($sd.table.row_h) { $rh = [double]$sd.table.row_h }
                $tb = $sl.Shapes.AddTable($rows, $cols, $L, $T, $tw, $rows * $rh)
                $tbl = $tb.Table
                $fs = 12; if ($sd.table.font) { $fs = [double]$sd.table.font }
                for ($c = 1; $c -le $cols; $c++) {
                    if ($sd.table.widths) { $tbl.Columns.Item($c).Width = $tw * [double]$sd.table.widths[$c - 1] }
                }
                for ($r = 1; $r -le $rows; $r++) {
                    for ($c = 1; $c -le $cols; $c++) {
                        $cell = $tbl.Cell($r, $c)
                        if ($r -eq 1) { $txt = [string]$sd.table.header[$c - 1] } else { $txt = [string]$sd.table.rows[$r - 2][$c - 1] }
                        $cell.Shape.TextFrame.TextRange.Text = $txt
                        $tr_ = $cell.Shape.TextFrame.TextRange; $tr_.Font.Name = "Calibri"; $tr_.Font.Size = $fs
                        $cell.Shape.TextFrame.MarginTop = 3; $cell.Shape.TextFrame.MarginBottom = 3; $cell.Shape.TextFrame.MarginLeft = 6; $cell.Shape.TextFrame.MarginRight = 6
                        if ($r -eq 1) { $cell.Shape.Fill.ForeColor.RGB = $NAVY; $tr_.Font.Color.RGB = $WHITE; $tr_.Font.Bold = -1 }
                        else {
                            $cell.Shape.Fill.ForeColor.RGB = $(if ($r % 2 -eq 0) { $WHITE } else { (C 241 245 249) })
                            $tr_.Font.Color.RGB = $INK; $tr_.Font.Bold = 0
                            if ($c -eq 1) { $tr_.Font.Bold = -1 }
                        }
                        if ($c -gt 1 -and $sd.table.numeric) { $tr_.ParagraphFormat.Alignment = 2 }
                    }
                }
                $newT = $T + $tb.Height + 14
                $BH = $BH - ($newT - $T); $T = $newT
            }
            $textW = $BW
            if ($sd.image) {
                $iw = $BW * [double]$sd.image_ratio
                $textW = $BW - $iw - 18
                if (-not $sd.bullets) { $textW = 0; $iw = $BW }
                $ip = Join-Path $Root $sd.image
                $pic = $sl.Shapes.AddPicture($ip, 0, -1, 0, 0)
                $pic.LockAspectRatio = -1
                $pic.Width = $iw
                if ($pic.Height -gt $BH) { $pic.Height = $BH }
                $pic.Left = $L + $BW - $pic.Width - [math]::Max(0, ($iw - $pic.Width) / 2); $pic.Top = $T + ($BH - $pic.Height) / 2
                if ($sd.image_border) { $pic.Line.Visible = -1; $pic.Line.ForeColor.RGB = (C 203 213 225); $pic.Line.Weight = 0.75 }
                if ($sd.image_caption) { Txt ($pic.Left) ($pic.Top + $pic.Height + 2) ($pic.Width) 16 $sd.image_caption 9 $MUTED $false 2 | Out-Null }
            }
            if ($sd.bullets -and $textW -gt 0) {
                $bx = $sl.Shapes.AddTextbox(1, $L, $T, $textW, $BH)
                $tf = $bx.TextFrame; $tf.WordWrap = -1; $tf.AutoSize = 0; $tf.VerticalAnchor = 1
                $tf.TextRange.Text = (($sd.bullets | ForEach-Object { if ($_ -is [string]) { $_ } else { $_.t } }) -join $N)
                $fsz = 18; if ($sd.font) { $fsz = [double]$sd.font }
                $tr_ = $tf.TextRange; $tr_.Font.Name = "Calibri"; $tr_.Font.Size = $fsz; $tr_.Font.Color.RGB = $INK
                $i = 0
                foreach ($b in $sd.bullets) {
                    $i++
                    $pp = $tr_.Paragraphs($i)
                    $lvl = 1; if ($b -isnot [string]) { $lvl = [int]$b.l }
                    $pp.ParagraphFormat.Bullet.Visible = -1
                    $pp.ParagraphFormat.Bullet.Character = 8226
                    $pp.ParagraphFormat.SpaceAfter = 6
                    $pp.IndentLevel = $lvl
                    if ($lvl -gt 1) { $pp.Font.Size = $fsz - 2; $pp.Font.Color.RGB = (C 51 65 85); $pp.ParagraphFormat.Bullet.Character = 8211 }
                }
                $bx.TextFrame.Ruler.Levels(1).FirstMargin = 0; $bx.TextFrame.Ruler.Levels(1).LeftMargin = 18
                $bx.TextFrame.Ruler.Levels(2).FirstMargin = 22; $bx.TextFrame.Ruler.Levels(2).LeftMargin = 40
                # bold lead-in up to the first colon
                $i = 0
                foreach ($b in $sd.bullets) {
                    $i++; $s_ = $(if ($b -is [string]) { $b } else { $b.t }); $k = $s_.IndexOf(":")
                    if ($k -gt 0 -and $k -lt 48) { $tr_.Paragraphs($i).Characters(1, $k + 1).Font.Bold = -1 }
                }
            }
            if ($sd.callout) {
                $cb = $sl.Shapes.AddShape(5, $L, 440, $BW, 62); $cb.Adjustments.Item(1) = 0.15
                $cb.Fill.Solid(); $cb.Fill.ForeColor.RGB = (C 240 253 250); $cb.Line.ForeColor.RGB = $TEAL; $cb.Line.Weight = 1; $cb.Shadow.Visible = 0
                $cb.TextFrame.TextRange.Text = $sd.callout
                StyleText $cb 14 (C 17 94 89) $false 1
                $cb.TextFrame.MarginLeft = 12; $cb.TextFrame.MarginRight = 12
            }
        }
        if ($sd.notes) { $sl.NotesPage.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text = $sd.notes }
    }
    $pp_ = Join-Path $Base "DentaMind_AI_Capstone_Presentation.pptx"
    $pdf = Join-Path $Base "DentaMind_AI_Capstone_Presentation.pdf"
    foreach ($f_ in @($pp_, $pdf)) { if (Test-Path $f_) { Remove-Item $f_ } }
    $p.SaveAs($pp_)
    $p.SaveAs($pdf, 32)
    $prev = Join-Path $Base "build\slide_png"
    New-Item -ItemType Directory -Force $prev | Out-Null
    Get-ChildItem $prev -Filter *.png | Remove-Item
    for ($i = 1; $i -le $p.Slides.Count; $i++) { $p.Slides.Item($i).Export((Join-Path $prev ("slide_{0:d2}.png" -f $i)), "PNG", 1600, 900) }
    $p.Close()
    Write-Output "presentation saved: $pp_ ($total slides)"
}
finally {
    $app.Quit() | Out-Null
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
}
