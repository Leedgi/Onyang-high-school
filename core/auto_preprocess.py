"""AI가 검출한 글자 위치·내용으로 전성분 영역을 고르고 영상 보정을 적용한다."""
from dataclasses import dataclass
import math
from statistics import median

import cv2
import numpy as np
from PIL import Image

from core.database import IngredientDatabase
from core.ingredient_text import heading_span, ingredient_drafts, section_end_span
from core.models import OCRResult


@dataclass(frozen=True)
class Region:
    box: tuple[int, int, int, int]
    method: str
    text_height: float
    score: float


def _line_regions(ocr: OCRResult):
    blocks = {block.source_index: block for block in ocr.blocks}
    output = []
    for line in ocr.lines:
        points = [point for index in line.source_indices if index in blocks for point in blocks[index].bbox]
        if points:
            xs, ys = zip(*points)
            output.append((line, (min(xs), min(ys), max(xs), max(ys))))
    return sorted(output, key=lambda item: item[1][1])


def locate_region(ocr: OCRResult, size: tuple[int, int], database: IngredientDatabase) -> Region:
    width, height = size
    rows = _line_regions(ocr)
    if not rows:
        return Region((0, 0, width, height), "not_found", 16, 0)
    seeds = []
    for index, (line, bounds) in enumerate(rows):
        if heading_span(line.raw_text):
            seeds.append((100.0, index, "heading"))
        elif not section_end_span(line.raw_text):
            subset = OCRResult("ok", line.raw_text, ocr.blocks, (line,))
            drafts = ingredient_drafts(subset, database)
            exact = sum(draft.status in {"exact", "alias"} for draft in drafts)
            if exact and (len(drafts) == 1 or exact / len(drafts) >= 0.35):
                seeds.append((10 + exact / max(1, len(drafts)), index, "dictionary"))
    if not seeds:
        return Region((0, 0, width, height), "not_found", 16, 0)
    score, start, method = max(seeds, key=lambda seed: (seed[0], -seed[1]))
    if method == "dictionary":
        # 표지를 놓쳤어도 중간의 잘 읽힌 줄만 자르지 않고 위의 인접한 성분 줄을 포함한다.
        while start > 0:
            previous, bounds = rows[start - 1]
            current = rows[start][1]
            previous_height, current_height = bounds[3] - bounds[1], current[3] - current[1]
            overlap = max(0, min(bounds[2], current[2]) - max(bounds[0], current[0]))
            if (section_end_span(previous.raw_text) or current[1] - bounds[3] > max(previous_height, current_height) * 2.2
                    or not 0.5 <= previous_height / max(1, current_height) <= 1.8
                    or overlap < min(bounds[2] - bounds[0], current[2] - current[0]) * 0.3):
                break
            start -= 1
    anchor = rows[start][1]
    typical = max(4.0, median(bounds[3] - bounds[1] for _, bounds in rows[start:]))
    selected = []
    stop_top = None
    previous_bottom = anchor[3]
    for line, bounds in rows[start:]:
        left, top, right, bottom = bounds
        if selected and section_end_span(line.raw_text):
            stop_top = top
            break
        if top - previous_bottom > typical * 2.2:
            break
        if selected and bottom - top > typical * 2.5:
            break
        # 다른 열·배경의 글자를 성분표와 합치지 않는다.
        overlap = max(0, min(right, anchor[2]) - max(left, anchor[0]))
        if overlap < min(right - left, anchor[2] - anchor[0]) * 0.15:
            continue
        selected.append(bounds)
        previous_bottom = max(previous_bottom, bottom)
    if not selected:
        return Region((0, 0, width, height), "not_found", typical, 0)
    pad = max(8, typical * 0.6)
    lower_edge = max(b[3] for b in selected) + pad
    if stop_top is not None:
        lower_edge = max(lower_edge, stop_top - max(2, typical * 0.15))
        lower_edge = min(lower_edge, stop_top)
    box = (
        max(0, math.floor(min(b[0] for b in selected) - pad)),
        max(0, math.floor(min(b[1] for b in selected) - pad)),
        min(width, math.ceil(max(b[2] for b in selected) + pad)),
        min(height, math.ceil(lower_edge)),
    )
    return Region(box, method, typical, score)


def estimate_skew(image: Image.Image) -> float:
    probe = image.copy()
    probe.thumbnail((1200, 800))
    gray = cv2.cvtColor(np.asarray(probe.convert("RGB")), cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 360, threshold=35,
                            minLineLength=max(30, probe.width // 8), maxLineGap=12)
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if -10 <= angle <= 10:
            angles.append(angle)
    return float(median(angles)) if len(angles) >= 3 else 0.0


def prepare_region(original: Image.Image, region: Region) -> tuple[Image.Image, Image.Image, dict, tuple[str, ...]]:
    left, top, right, bottom = region.box
    if not (0 <= left < right <= original.width and 0 <= top < bottom <= original.height):
        raise ValueError("자동 검출된 영역 좌표가 이미지 범위를 벗어났습니다.")
    cropped = original.crop(region.box)
    angle = estimate_skew(cropped)
    corrected = cropped.rotate(angle, Image.Resampling.BICUBIC, expand=True, fillcolor="white") if abs(angle) >= 0.3 else cropped.copy()
    scale = min(3.0, max(1.0, 64 / region.text_height), 2400 / corrected.width, 1600 / corrected.height)
    resized = corrected.resize((max(8, round(corrected.width * scale)), max(8, round(corrected.height * scale))), Image.Resampling.LANCZOS)
    array = np.asarray(resized.convert("RGB"))
    lab = cv2.cvtColor(array, cv2.COLOR_RGB2LAB)
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(lab[:, :, 0])
    enhanced = Image.fromarray(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB))
    gray = cv2.cvtColor(np.asarray(cropped.convert("RGB")), cv2.COLOR_RGB2GRAY)
    warnings = []
    if region.text_height < 12:
        warnings.append("원본의 글씨가 작습니다. 확대 인식 후에도 빠진 글자는 원본과 비교해 주세요.")
    if cv2.Laplacian(gray, cv2.CV_64F).var() < 20:
        warnings.append("글자 영역이 흐리거나 대비가 낮습니다. 원본에서 사라진 글자는 복원할 수 없습니다.")
    metadata = {"region_method": region.method, "crop_box": region.box,
                "deskew_degrees": angle, "scale": scale, "image_size": resized.size,
                "bbox_coordinate_system": "selected processed image pixels"}
    return resized, enhanced, metadata, tuple(warnings)


def curved_text_variant(image: Image.Image, text_height: float) -> tuple[Image.Image, dict]:
    """인접 글자 줄의 휨을 추정하고 제한된 원통 가설을 대안 영상으로 만든다.

    원본을 대체하지 않는다. 실제 원통 반지름 측정이나 없어진 글자 복원이 아니다.
    """
    rgb = np.asarray(image.convert("RGB"))
    height, width = rgb.shape[:2]
    if min(height, width) < 16:
        raise ValueError("곡면 보정에 필요한 영상 크기가 부족합니다.")
    line_height = float(np.clip(text_height, 12, max(12, height / 3)))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    block = max(15, int(line_height * 2) | 1)
    ink = 255 - cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                      cv2.THRESH_BINARY, block, 13)
    profiles = []
    centers = np.linspace(-.85, .85, 9)
    for center in centers:
        x = int((center + 1) * .5 * width)
        half = max(4, width // 13)
        profile = ink[:, max(0, x-half):min(width, x+half)].mean(axis=1).astype(np.float32)
        profile = cv2.GaussianBlur(profile.reshape(-1, 1), (1, 5), 0).ravel()
        profiles.append(profile)
    reference = profiles[4]
    distance = max(5, int(line_height * .8))
    maxima = cv2.dilate(reference.reshape(-1, 1), np.ones((distance, 1), np.uint8)).ravel()
    peaks = np.flatnonzero((reference >= maxima - .01) & (reference > max(8, float(reference.max()) * .3)))
    merged = []
    for peak in peaks:
        if not merged or peak - merged[-1] > distance:
            merged.append(int(peak))
        elif reference[peak] > reference[merged[-1]]:
            merged[-1] = int(peak)
    max_shift = max(3, int(line_height * .55))
    radius = max(5, int(line_height * .65))
    fits = []
    for peak in merged:
        start, stop = peak-radius, peak+radius+1
        if start-max_shift < 0 or stop+max_shift > height:
            continue
        target = reference[start:stop] - reference[start:stop].mean()
        xs, shifts = [], []
        for center, profile in zip(centers, profiles):
            best = (-1., 0)
            for shift in range(-max_shift, max_shift+1):
                sample = profile[start+shift:stop+shift]
                sample = sample - sample.mean()
                denominator = float(np.linalg.norm(target) * np.linalg.norm(sample))
                correlation = float(np.dot(target, sample) / denominator) if denominator > 1 else 0.
                # 동점이면 원래 위치를 우선한다.
                if correlation > best[0] + .001 or abs(correlation-best[0]) <= .001 and abs(shift) < abs(best[1]):
                    best = (correlation, shift)
            if best[0] >= .5:
                xs.append(center)
                shifts.append(best[1])
        if len(xs) < 7:
            continue
        fit = np.polyfit(xs, shifts, 2)
        error = float(np.sqrt(np.mean((np.polyval(fit, xs)-shifts)**2)))
        if error < line_height * .16:
            fits.append(fit)
    coefficients = np.zeros(3)
    detected = False
    if len(fits) >= 2:
        coefficients = np.median(fits, axis=0)
        agreement = np.mean([np.sign(f[0]) == np.sign(coefficients[0]) for f in fits])
        detected = abs(coefficients[0]) >= 3 and agreement >= .9
        if not detected:
            coefficients[:] = 0
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    output_u = x / max(1, width-1) * 2 - 1
    theta = .65  # Bounded alternative, not a measured camera/cylinder parameter.
    source_u = np.sin(output_u * theta) / math.sin(theta)
    source_x = (source_u+1) * .5 * (width-1)
    offsets = np.clip(np.polyval(coefficients, source_u), -max_shift, max_shift)
    source_y = y + offsets
    map1, map2 = cv2.convertMaps(source_x.astype(np.float32), source_y.astype(np.float32), cv2.CV_16SC2)
    corrected = cv2.remap(rgb, map1, map2, cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
    return Image.fromarray(corrected), {
        "curve_detected": bool(detected), "supporting_rows": len(fits),
        "vertical_curve_coefficients": coefficients.tolist(),
        "max_vertical_shift": float(np.max(np.abs(offsets))),
        "horizontal_hypothesis_radians": theta,
        "note": "제한된 곡면 보정 가설이며 실제 측정 기하나 정답 확률이 아닙니다.",
    }


def rectified_text_rows(image: Image.Image, text_height: float, theta: float = 0.0):
    """검출 영역의 인쇄 줄을 각각 추적해 편다. 원본 좌표는 추적 정보에 남긴다."""
    rgb=np.asarray(image.convert('RGB'));height,width=rgb.shape[:2]
    if min(height,width)<24 or not 0<=theta<=1.1:
        raise ValueError('줄 보정 입력 범위를 확인해 주세요.')
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    if np.median(gray)<100:gray=255-gray
    nominal=float(np.clip(text_height,12,height/2))
    block=max(15,int(nominal*1.5)|1)
    ink=255-cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,block,13)
    count,labels,stats,_=cv2.connectedComponentsWithStats(ink,8)
    character_heights=[]
    for _,_,w,h,area in stats[1:]:
        if max(6,nominal*.2)<=h<=nominal*1.6 and 2<=w<=nominal*2 and area>=8:
            character_heights.append(h)
    char_height=float(median(character_heights)) if len(character_heights)>=12 else nominal*.6
    char_height=max(char_height,nominal*.5)
    centers=np.linspace(.04,.96,25)
    profiles=[]
    for center in centers:
        x=round(center*(width-1));half=max(4,width//30)
        profile=ink[:,max(0,x-half):min(width,x+half+1)].mean(axis=1).astype(np.float32)
        sigma=max(1,char_height*.08)
        profiles.append(cv2.GaussianBlur(profile.reshape(-1,1),(1,0),sigmaY=sigma,sigmaX=0).ravel())
    def peaks(profile):
        distance=max(9,int(char_height*.9))
        maxima=cv2.dilate(profile.reshape(-1,1),np.ones((distance*2+1,1),np.uint8)).ravel()
        found=np.flatnonzero((profile>=maxima-.01)&(profile>max(3,profile.max()*.18)))
        selected=[]
        for point in sorted(found,key=lambda p:-profile[p]):
            if all(abs(point-other)>=distance for other in selected):selected.append(int(point))
        return sorted(selected)
    options=[]
    for i in range(25):
        found=peaks(profiles[i]);intervals=np.diff(found)
        irregularity=float(np.std(intervals)/max(1,np.mean(intervals))) if len(intervals) else 1.
        options.append((len(found)-abs(centers[i]-.5)*.3-irregularity*3,i,found))
    _,reference,seeds=max(options)
    if not 2<=len(seeds)<=30:
        raise ValueError('독립된 인쇄 줄을 충분히 추적하지 못했습니다.')
    pitch=float(median(np.diff(seeds)))
    if pitch<char_height*1.05:
        raise ValueError('글자 획과 인쇄 줄을 구분하지 못했습니다.')
    char_height=max(char_height,pitch*.58)
    def centroid(profile,point):
        radius=max(5,round(pitch*.40));a=max(0,round(point)-radius);b=min(height,round(point)+radius+1)
        values=np.maximum(profile[a:b]-max(1,float(profile.max())*.08),0)
        return float(np.dot(np.arange(a,b),values)/values.sum()) if values.sum()>1 else float(point)
    fits=[];traces=[]
    for seed in seeds:
        points={reference:centroid(profiles[reference],seed)}
        for step in (-1,1):
            previous=points[reference];before=previous
            for i in range(reference+step,25 if step==1 else -1,step):
                prediction=previous+np.clip(previous-before,-pitch*.18,pitch*.18)
                radius=round(pitch*.30);a=max(0,round(prediction)-radius);b=min(height,round(prediction)+radius+1)
                values=profiles[i][a:b]
                if len(values)==0 or values.max()<max(3,profiles[i].max()*.12):continue
                score=values/max(1,float(values.max()))-abs(np.arange(a,b)-prediction)/pitch*.8
                point=centroid(profiles[i],a+int(np.argmax(score)))
                if abs(point-previous)>pitch*.42:continue
                points[i]=point;before,previous=previous,point
        xs=np.array([centers[i]*2-1 for i in points]);ys=np.array(list(points.values()))
        degree=2 if len(points)>=8 and np.ptp(xs)>=.5 else 1 if len(points)>=3 else 0
        fit=np.polyfit(xs,ys,degree)
        for _ in range(2):
            residual=abs(np.polyval(fit,xs)-ys);keep=residual<max(3,pitch*.16)
            if keep.sum()<max(3,degree+2):break
            fit=np.polyfit(xs[keep],ys[keep],degree)
        error=float(np.sqrt(np.mean((np.polyval(fit,xs)-ys)**2)))
        if error>pitch*.22:continue
        fits.append(fit);traces.append({'seed':int(seed),'support':len(points),'rms_pixels':error,'coefficients':fit.tolist(),'horizontal_support_range':[float(xs.min()),float(xs.max())]})
    if len(fits)<2 or len(fits)<len(seeds)*.8:
        raise ValueError('줄 추적이 불완전해 원래 인식 경로를 유지합니다.')
    # 한 글자 안의 획 두 개가 별도 줄의 씨앗으로 잡혔어도 추적 결과가 같은 줄이면 합친다.
    unique_fits, unique_traces = [], []
    sample_x = np.linspace(-.9, .9, 31)
    for fit, trace in zip(fits, traces):
        if unique_fits:
            previous = np.polyval(unique_fits[-1], np.clip(sample_x, *unique_traces[-1]['horizontal_support_range']))
            current = np.polyval(fit, np.clip(sample_x, *trace['horizontal_support_range']))
            if np.median(abs(current-previous)) < pitch*.45 and np.max(abs(current-previous)) < pitch*.8:
                if trace['rms_pixels'] < unique_traces[-1]['rms_pixels']:
                    unique_fits[-1], unique_traces[-1] = fit, trace
                continue
        unique_fits.append(fit); unique_traces.append(trace)
    fits, traces = unique_fits, unique_traces
    if len(fits)<2:
        raise ValueError('독립된 인쇄 줄을 충분히 추적하지 못했습니다.')
    pitch=float(median(np.diff([np.polyval(f,np.clip(0,*t['horizontal_support_range'])) for f,t in zip(fits,traces)])))
    char_height=max(char_height,pitch*.58)
    # 이웃 줄 사이의 범위에서 글자 중심을 다시 구한다. 획의 봉우리를 기준선으로 오인하지 않는다.
    sample_u=centers*2-1
    for iteration in range(2):
        predicted=np.array([np.polyval(f,np.clip(sample_u,*t['horizontal_support_range'])) for f,t in zip(fits,traces)])
        refined=[]
        for i,(fit,trace) in enumerate(zip(fits,traces)):
            xs,ys=[],[]
            for j,profile in enumerate(profiles):
                if not trace['horizontal_support_range'][0]-.04<=sample_u[j]<=trace['horizontal_support_range'][1]+.04:continue
                before=predicted[i,j]-predicted[i-1,j] if i else predicted[1,j]-predicted[0,j]
                after=predicted[i+1,j]-predicted[i,j] if i+1<len(fits) else before
                a=max(0,round(predicted[i,j]-before*.48));b=min(height,round(predicted[i,j]+after*.48)+1)
                values=profile[a:b]
                if len(values)==0 or values.max()<max(3,profile.max()*.12):continue
                values=np.maximum(values-max(1,float(values.max())*.08),0)
                if values.sum()<=1:continue
                xs.append(sample_u[j]);ys.append(float(np.dot(np.arange(a,b),values)/values.sum()))
            if xs:
                degree=4 if len(xs)>=15 and np.ptp(xs)>=1.2 else 2 if len(xs)>=8 else 1 if len(xs)>=3 else 0
                fit=np.polyfit(xs,ys,degree)
                trace={**trace,'coefficients':fit.tolist(),'support':len(xs),
                       'horizontal_support_range':[float(min(xs)),float(max(xs))],
                       'rms_pixels':float(np.sqrt(np.mean((np.polyval(fit,xs)-ys)**2)))}
            refined.append((fit,trace))
        fits=[item[0] for item in refined];traces=[item[1] for item in refined]
    x=np.arange(width,dtype=np.float32);u=x/max(1,width-1)*2-1
    source_u=np.sin(u*theta)/math.sin(theta) if theta else u
    source_x=(source_u+1)*.5*(width-1)
    baselines=np.array([np.polyval(fit,np.clip(source_u,*trace['horizontal_support_range'])) for fit,trace in zip(fits,traces)])
    gaps=np.diff(baselines,axis=0)
    if gaps.min()<pitch*.35:
        raise ValueError('추적한 줄들이 겹쳐 원래 인식 경로를 유지합니다.')
    row_height=max(17,round(pitch*.92))
    rows=[]
    for i,baseline in enumerate(baselines):
        upper=gaps[i-1] if i else gaps[0]
        lower=gaps[i] if i<len(gaps) else gaps[-1]
        half=np.clip(np.minimum(upper,lower)*.46,pitch*.30,pitch*.75)
        source_y=np.linspace(-1,1,row_height,dtype=np.float32)[:,None]*half[None,:]+baseline[None,:]
        source_x_map=np.broadcast_to(source_x,(row_height,width)).astype(np.float32)
        m1,m2=cv2.convertMaps(source_x_map,source_y.astype(np.float32),cv2.CV_16SC2)
        row=cv2.remap(rgb,m1,m2,cv2.INTER_CUBIC,borderMode=cv2.BORDER_CONSTANT,borderValue=(255,255,255))
        # 글자 가장자리가 영상 경계에 닿지 않게 여백을 둔다.
        pad=max(6,round(char_height*.25))
        padded=cv2.copyMakeBorder(row,pad,pad,pad,pad,cv2.BORDER_CONSTANT,value=(255,255,255))
        scale=min(2.,max(1.,64/row_height),2600/padded.shape[1])
        patch=Image.fromarray(padded).resize((round(padded.shape[1]*scale),round(padded.shape[0]*scale)),Image.Resampling.LANCZOS)
        rows.append(patch)
    return tuple(rows),{'method':'tracked_rows','row_count':len(rows),'pitch':pitch,'character_height':char_height,
                        'horizontal_hypothesis_radians':theta,'rows_in_source_image':traces,
                        'note':'글자 줄 추적에 따른 보정 가설이며 실제 원통 반지름이나 정답 확률이 아닙니다.'}
