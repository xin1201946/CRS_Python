import math
import random
import numpy as np
import os
from math import sin,cos,radians,fabs
import cv2
import matplotlib.pyplot as plt
from yolov5 import YOLOv5

# 使用 YOLO 加载器加载模型
model = YOLOv5('./library/clear_pic/NumVision.pt')  # 加载自定义模型
model.conf = 0.6  # 设置置信度阈值
colors = plt.cm.get_cmap('tab10')(range(10))
colors = (colors * 255).astype(int)
def main(img,save_Path=None,filename=None):
    """
    进行处理图片
    :param img: 二值化后的图像
    :param save_Path:保存位置
    :return: 经过裁剪的图像
    """
    imgs= process_image_file(img,save_Path,filename)
    return imgs


def crop_and_save(img, detections, save_dir='./cache/',filename='crop'):
    """
    将图像裁剪到模型识别到的区域，并保存到指定文件夹

    Args:
        img: 原图
        detections: 模型检测结果，列表类型，每个元素为[x1, y1, x2, y2, confidence, class]
        save_dir: 保存裁剪图像的文件夹路径
    """
    # 创建保存文件夹
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    cropped_img = img
    # 如果检测结果为空，则保存原图
    if not detections:
        cv2.imwrite(os.path.join(save_dir, f'{filename}.jpg'), img)
        return img

    # 裁剪并保存检测区域
    for i, detection in enumerate(detections):
        x1, y1, x2, y2, _, _ = detection
        cropped_img = img[int(y1):int(y2), int(x1):int(x2)]
        # 保存裁剪图像
        cv2.imwrite(os.path.join(save_dir, f'{filename}.jpg'), cropped_img)
    return cropped_img


def plot_one_box(x, img, color=None, label=None, line_thickness=3):
    """
    Draws a box on an image with optional label

    Args:
        x: Bounding box coordinates in (top, left, bottom, right) format
        img: Image to draw on
        color: Color to draw box
        label: Optional label to display
        line_thickness: Thickness of the box lines
    """

    tl = round(0.002 * (img.shape[0] + img.shape[1]) / 2) + 1  # line/font thickness
    if color is None:
        color = [random.randint(0, 255) for _ in range(3)]  # Generate random color if not provided
    c1, c2 = (int(x[0]), int(x[1])), (int(x[2]), int(x[3]))
    cv2.rectangle(img, c1, c2, color, thickness=tl, lineType=cv2.LINE_AA)
    if label:
        tf = max(tl - 1, 1)  # font thickness
        t_size = cv2.getTextSize(label, 0, fontScale=tl / 3, thickness=tf)[0]
        c2 = c1[0] + t_size[0], c1[1] - t_size[1] - 3
        cv2.rectangle(img, c1, c2, color, -1, cv2.LINE_AA)  # filled
        cv2.putText(img, label, (c1[0], c1[1] - 2), 0, tl / 3, [225, 255, 255], thickness=tf, lineType=cv2.LINE_AA)


def correct_orientation(cropped_img):
    # 转换为灰度图
    gray_image = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2GRAY)

    # 使用自适应阈值增强边缘检测效果
    thresh = cv2.adaptiveThreshold(gray_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)

    # 霍夫直线变换
    lines = cv2.HoughLinesP(thresh, 1, np.pi / 180, 100, minLineLength=50, maxLineGap=10)

    if lines is not None and len(lines) > 0:
        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
            angles.append(angle)

        avg_angle = np.mean(angles)
        corrected_img = rotate_image(cropped_img, avg_angle)

        return corrected_img
    else:
        print("未检测到框选区域")
        return cropped_img


def rotate_image(image, angle):
    """旋转图像到指定角度"""
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, -angle, 1.0)
    rotated_img = cv2.warpAffine(image, M, (w, h))
    return rotated_img


def rotated_img_with_fft(gray):
    # 图像延扩
    gray_image = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    h, w = gray_image.shape[:2]
    new_h = cv2.getOptimalDFTSize(h)
    new_w = cv2.getOptimalDFTSize(w)
    right = new_w - w
    bottom = new_h - h
    nimg = cv2.copyMakeBorder(gray_image, 0, bottom, 0, right, borderType=cv2.BORDER_CONSTANT, value=0)

    # 执行傅里叶变换，并过得频域图像
    f = np.fft.fft2(nimg)
    fshift = np.fft.fftshift(f)

    fft_img = np.log(np.abs(fshift))
    fft_img = (fft_img - np.amin(fft_img)) / (np.amax(fft_img) - np.amin(fft_img))

    fft_img *= 255
    ret, thresh = cv2.threshold(fft_img, 150, 255, cv2.THRESH_BINARY)

    # 霍夫直线变换
    thresh = thresh.astype(np.uint8)
    lines = cv2.HoughLinesP(thresh, 1, np.pi / 180, 30, minLineLength=40, maxLineGap=100)
    try:
        lines1 = lines[:, 0, :]
    except Exception as e:
        lines1 = []
    piThresh = np.pi / 180
    pi2 = np.pi / 2
    angle = 0
    for line in lines1:
        # x1, y1, x2, y2 = line[0]
        x1, y1, x2, y2 = line
        # cv2.line(lineimg, (x1, y1), (x2, y2), (0, 255, 0), 2)
        if x2 - x1 == 0:
            continue
        else:
            theta = (y2 - y1) / (x2 - x1)
        if abs(theta) < piThresh or abs(theta - pi2) < piThresh:
            continue
        else:
            angle = abs(theta)
            break

    angle = math.atan(angle)
    angle = angle * (180 / np.pi)
    print(angle)
    # cv2.imshow("line image", lineimg)
    center = (w // 2, h // 2)
    height_1 = int(w * fabs(sin(radians(angle))) + h * fabs(cos(radians(angle))))
    width_1 = int(h * fabs(sin(radians(angle))) + w * fabs(cos(radians(angle))))
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    M[0, 2] += (width_1 - w) / 2
    M[1, 2] += (height_1 - h) / 2
    rotated = cv2.warpAffine(gray_image, M, (width_1, height_1), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    cv2.imshow('rotated', rotated)
    cv2.waitKey(0)
    return rotated


def rotated_img_with_radiation(gray, is_show=False):
    gray_image = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray_image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
    if is_show:
        cv2.imshow('thresh', thresh)

    coords = np.column_stack(np.where(thresh > 0))
    angle = cv2.minAreaRect(coords)[-1]
    print(angle)

    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    rotated = rotate_image(gray_image, angle)

    if is_show:
        cv2.putText(rotated, 'Angle: {:.2f} degrees'.format(angle), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 0, 255), 2)
        cv2.imshow('Rotated', rotated)
        cv2.waitKey()

    return rotated


def get_angle_from_lines(lines):
    """计算霍夫变换得到的线的平均角度"""
    if lines is None or len(lines) == 0:
        return 0

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
        angles.append(angle)

    return np.mean(angles)


# 处理主调函数
def process_image(cropped_img):
    corrected_img = correct_orientation(cropped_img)
    radiation_corrected_img = rotated_img_with_fft(corrected_img)

    return radiation_corrected_img


def process_image_file(img_path,save_Path,filename):
    img_np = np.array(img_path)

    # 调整图像大小（根据模型设置调整）
    img_resized = cv2.resize(img_np, (640, 640))  # 注意cv2.resize需要的是高宽顺序

    results = model.predict(img_resized)  # 正确的调用方式
    img = np.array(img_resized)

    # 可视化结果
    detections = results.xyxy[0].tolist()  # Convert results to a list of detections

    # Draw bounding boxes and labels on the image
    for *xyxy, conf, cls in detections:
        label = f'{results.names[int(cls)]} {conf:.2f}'  # 使用 results.names 而不是 model.names
        color = (255, 0, 0)  # Red (adjust as needed)
        plot_one_box(xyxy, img, label=label, color=color, line_thickness=3)
    if save_Path is not None:
        imgs = crop_and_save(img, results.xyxy[0].tolist(),save_Path,filename)
    else:
        imgs = crop_and_save(img, results.xyxy[0].tolist())
    return imgs
