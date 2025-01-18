import os
import pathlib
import cv2
import numpy as np
from ultralytics import YOLO

temp=pathlib.PosixPath
pathlib.PosixPath=pathlib.WindowsPath
# 加载模型
model = YOLO("./library/get_num/num-cls-yolo11n-v3.pt")

def compute_skew(image):
    # 确保图像是灰度的
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # 边缘检测
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # 霍夫线变换
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 100)

    angles = []

    if lines is not None:
        for line in lines:
            rho, theta = line[0]
            # 只考虑接近水平或垂直的线
            if theta < np.pi / 4 or theta > 3 * np.pi / 4:
                angles.append(theta)

    # 计算中位数角度
    if len(angles) > 0:
        median_angle = np.median(angles)
        # 将角度转换为度数
        skew_angle = np.rad2deg(median_angle - np.pi / 2)
        return skew_angle
    else:
        return 0


def deskew(image):
    # Invert the image for moment calculation
    img = 255 - image

    # Calculate moments
    moments = cv2.moments(img)
    if abs(moments['mu02']) < 1e-2:
        return image

    # Calculate skew
    skew = moments['mu11'] / moments['mu02']
    M = np.float32([[1, skew, -0.5 * img.shape[0] * skew],
                    [0, 1, 0]])

    # Apply affine transform
    height, width = img.shape
    img = cv2.warpAffine(img, M, (width, height),
                         flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR)

    # Invert back
    return 255 - img


def load_image(path, show_pic=False, show_lowPic=False):
    # Read the image
    image = cv2.imread(path)
    if image is None:
        raise ValueError("Error: Could not load image. Please check the file path.")
    resized_image = cv2.resize(image, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    # Convert to grayscale
    gray_image = cv2.cvtColor(resized_image, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur to reduce noise
    blurred = cv2.GaussianBlur(gray_image, (5, 5), 0)

    # Apply adaptive thresholding
    binary = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,  # Changed to BINARY to make background white
        11,
        2
    )

    # Create kernels for morphological operations
    kernel_small = np.ones((2, 2), np.uint8)
    kernel_medium = np.ones((3, 3), np.uint8)

    # Clean up noise
    denoised = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_small)

    # Fill small holes in the digits
    filled = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel_medium)

    # Remove isolated pixels
    cleaned = cv2.medianBlur(filled, 3)

    # Resize if needed (using better interpolation)
    if max(cleaned.shape) < 28:  # Minimum size for good recognition
        scale = 28 / min(cleaned.shape)
        cleaned = cv2.resize(cleaned, None, fx=scale, fy=scale,
                             interpolation=cv2.INTER_LANCZOS4)

    # Apply contour filtering to remove small artifacts
    contours, _ = cv2.findContours(255 - cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask = np.ones_like(cleaned) * 255
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 50:  # Adjust threshold based on your image size
            cv2.drawContours(mask, [contour], -1, 0, -1)

    final_image = cv2.bitwise_or(cleaned, mask)

    # Deskew if needed
    final_image = deskew(final_image)

    if show_pic:
        if show_lowPic:
            cv2.imshow('Original', gray_image)
            cv2.imshow('After Preprocessing', binary)
        cv2.imshow('Final Result', final_image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return final_image

def save_files(path, save_name, img):
    if isinstance(path, np.ndarray):
        print("Error: path is an ndarray, converting to string")
        path = str(path)
    if not os.path.exists(path):
        os.makedirs(path)
    full_path = os.path.join(path, save_name)
    print(f"Saving image to: {full_path}")
    cv2.imwrite(full_path, img)

def main(save_path="./Out_PIC/", save_name='result.jpg', save_file=True, show_result=True):
    img_path = './cache/crop.jpg'
    img = load_image(img_path, show_pic=False)

    # 使用模型进行推理
    resized_image = cv2.resize(img, (224, 224), interpolation=cv2.INTER_CUBIC)
    model = YOLO("./library/get_num/num-cls-yolo11n-v2.pt")
    results = model.predict(source=resized_image, save=False)

    class_name = ""
    confidence = 0.0
    for result in results:
        probs = result.probs
        class_id = probs.top1
        class_name = model.names[class_id]
        confidence = probs.top1conf.item()
        print(f"Recognized Class: {class_name}")
        print(f"Confidence: {confidence:.2f}")

    # 在图像上绘制结果
    result_img = cv2.resize(img, (448, 448))  # 放大图像以便更好地显示
    cv2.putText(result_img, f"Class: {class_name}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(result_img, f"Conf: {confidence:.2f}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    if save_file:
        save_files(save_path, save_name, result_img)

    if show_result:
        cv2.imshow('Recognition Result', result_img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return class_name