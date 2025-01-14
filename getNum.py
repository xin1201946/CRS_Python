import library.clear_pic.main as clearp
import library.get_num.NewMain as newNumV
import os
from PIL import Image

def get_pic(path):
    """
    使用get_pic(path[可省])后在调用其他函数！
    :param path: 图片路径
    :return: 二值化，伽马矫正，对比度调整的图像
    """

    pic_path = path if path is not None else './flask-dist/UPLOAD/pic'
    img = Image.open(pic_path)
    bw_img = img.convert('L')  #灰度图像
    return bw_img


def cut_pic(img):
    '''
    使用剪切模型定位数字区域
    :param img: 经过二值化的图像
    :return: 裁剪后的图像
    '''
    return clearp.main(img)


def get_num(_,save_path='D:/hbsoftware/AIFlask/result/',save=False,save_name='') -> str:
    '''
    使用模型获取数值
    :return: 数字文本 (str)
    '''
    return newNumV.main(save_file=save,save_path=save_path,save_name=save_name,show_result=False)

def quick_cut_img(path):
    for filename in os.listdir(path):
        # 构建完整的文件路径
        file_path = os.path.join(path, filename)
        print(file_path)
        get_num(cut_pic(get_pic(file_path)),save=True,save_name=filename)
    return True

def process_image(image_path, save_path=None):
    """
    处理图片，获取文字结果并按格式保存到result.txt中（如果save_path指定）
    :param image_path: 图片文件路径，可以是单个文件路径也可以是包含图片文件的目录路径
    :param save_path: 保存结果文件的路径，为None则不保存
    """
    if os.path.isfile(image_path):
        # 如果给定的是单个文件路径
        file_name = os.path.basename(image_path)
        result_text = get_num(image_path)
        content_to_write = f"// This software uses YOLO V5, V11 for text recognition.\n--------------------------------------------------------------\n{file_name} - {result_text}\n"
        if save_path:
            result_file_path = os.path.join(save_path, "result.txt")
            with open(result_file_path, "a", encoding="utf-8") as f:
                f.write(content_to_write)
        return content_to_write
    elif os.path.isdir(image_path):
        # 如果给定的是目录路径
        all_content_to_write = ""
        for root, dirs, files in os.walk(image_path):
            for file in files:
                file_full_path = os.path.join(root, file)
                file_name = os.path.basename(file_full_path)
                result_text = get_num(file_full_path)
                single_content = f"// This software uses YOLO V5, V11 for text recognition.\n--------------------------------------------------------------\n{file_name} - {result_text}\n"
                all_content_to_write += single_content
                if save_path:
                    result_file_path = os.path.join(save_path, "result.txt")
                    with open(result_file_path, "a", encoding="utf-8") as f:
                        f.write(single_content)
        return all_content_to_write
    else:
        raise ValueError("给定的路径既不是有效的文件路径也不是有效的目录路径")

def auto_run(path: None):
    """
    一键调用
    :param path: 图像路径，可为空
    :return: 数字文本 (str)
    """
    return get_num(cut_pic(get_pic(path)))
