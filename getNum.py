from CCRS_Library import (
    new_clear_pic as clear_pic_11,
    clear_pic as clear_pic_5,
    get_num_obb,
    get_num_cls,
    get_num_obj,
    insert_recognition_record as insert_hub_info,
    check_and_create_database,
)
import os
from PIL import Image


def get_pic(path):
    """
    使用get_pic(path[可省])后在调用其他函数！
    调用此函数后再调用其他函数！
    :param path: 图片路径
    :param path: Image path
    :return: 二值化，伽马矫正，对比度调整的图像
    :return: An image that has undergone binarization, gamma correction, and contrast adjustment
    """
    print(path)
    pic_path = path if path is not None else "./flask-dist/UPLOAD/pic"
    img = Image.open(pic_path)
    bw_img = img.convert("L")  # 灰度图像
    # Convert the image to grayscale
    return bw_img


def cut_pic(img):
    """
    使用剪切模型定位数字区域
    Use the cutting model to locate the digit area
    :param img: 经过二值化的图像
    :param img: Binarized image
    :return: 裁剪后的图像
    :return: Cropped image
    """
    return clear_pic_11(img)


def get_num(
    _,
    save_path="D:/hbsoftware/AIFlask/result/",
    save=False,
    save_name="",
    load_imagePath=None,
) -> str:
    """
    使用模型获取数值
    Use the model to obtain the numerical value
    :return: 数字文本 (str)
    :return: Digital text (str)
    """
    return get_num_cls(
        save_file=save,
        save_path=save_path,
        save_name=save_name,
        show_result=False,
        load_imagePath=load_imagePath,
    )


def quick_cut_img(path, savepath):
    # 检查保存路径是否为空
    # Check if the save path is empty
    if savepath is None:
        return "No SavePath?"
    # 检查保存路径是否存在，如果不存在则创建
    # Check if the save path exists, create it if it doesn't
    if not os.path.exists(savepath):
        os.makedirs(savepath)
        print(f"Save directory '{savepath}' does not exist. Created successfully.")
    # 遍历指定路径下的所有文件
    # Iterate over all files in the specified path
    for filename in os.listdir(path):
        # 构建完整的文件路径
        # Build the full file path
        file_path = os.path.join(path, filename)
        print(file_path)
        if filename.endswith(".jpg") or filename.endswith(".png"):
            img, paths = clear_pic_11(get_pic(file_path))
            get_num_cls(
                save_path=savepath,
                save_name=filename,
                save_file=True,
                load_imagePath=paths[0],
                allow_Null=False,
            )
    return True


def process_image(image_path, save_path=None):
    """
    处理图片，获取文字结果并按格式保存到result.txt中（如果save_path指定）
    Process the image, obtain the text result and save it in result.txt in the specified format (if save_path is specified)
    :param image_path: 图片文件路径，可以是单个文件路径也可以是包含图片文件的目录路径
    :param image_path: Image file path, can be a single file path or a directory path containing image files
    :param save_path: 保存结果文件的路径，为None则不保存
    :param save_path: Path to save the result file, do not save if it is None
    """
    # 检查给定的路径是否为单个文件
    # Check if the given path is a single file
    if os.path.isfile(image_path):
        # 如果给定的是单个文件路径
        # If a single file path is given
        file_name = os.path.basename(image_path)
        result_text = get_num(image_path)
        content_to_write = f"{file_name} - {result_text}\n"
        # 如果指定了保存路径
        # If a save path is specified
        if save_path:
            result_file_path = os.path.join(save_path, "result.txt")
            with open(result_file_path, "a", encoding="utf-8") as f:
                f.write(content_to_write)
        else:
            print("No save path specified, will save to the database")
            check_and_create_database("./db/data.db")
            insert_hub_info("./db/data.db", result_text)

        return content_to_write
    # 检查给定的路径是否为目录
    # Check if the given path is a directory
    elif os.path.isdir(image_path):
        # 如果给定的是目录路径
        # If a directory path is given
        all_content_to_write = ""
        # 遍历目录下的所有文件
        # Iterate over all files in the directory
        for root, dirs, files in os.walk(image_path):
            for file in files:
                file_full_path = os.path.join(root, file)
                file_name = os.path.basename(file_full_path)
                print(file_full_path + file_name)
                new_result_text = New_auto_run(file_full_path)
                single_content = f"{file_name} - {new_result_text}\n"
                all_content_to_write += single_content
                # 如果指定了保存路径
                # If a save path is specified
                if save_path:
                    result_file_path = os.path.join(save_path, "result.txt")
                    with open(result_file_path, "a", encoding="utf-8") as f:
                        f.write(single_content)
                else:
                    print("No save path specified, will save to the database")
                    check_and_create_database("./db/data.db")
                    insert_hub_info("./db/data.db", new_result_text)
        return all_content_to_write
    else:
        raise ValueError(
            "The given image_path is neither a valid file path nor a valid directory path"
        )


def New_auto_run(path: None, Clear_Pic_model_version="11", OCR_model_type="cls"):
    """
    一键调用
    One-click call
    :param path: 图像路径，可为空
    :param Clear_Pic_model_version: 裁剪模型版本,默认为'11',可选 '5'
    :param OCR_model_type: 识别模型类型,默认为'obb',可选 'obj' 和 'cls'
    :param path: Image path, can be empty
    :param Clear_Pic_model_version: Crop model version, default is '11', optional '5'
    :param OCR_model_type: Identify the model type, default is 'obb', optional 'obj' and 'cls'
    :return: 数字文本 (str)
    :return: Digital text (str)
    """
    print(Clear_Pic_model_version, OCR_model_type)
    if Clear_Pic_model_version == "11":
        img, paths = clear_pic_11(get_pic(path))
    else:
        img, paths = clear_pic_5(get_pic(path))

    if OCR_model_type == "obb":
        return get_num_obb(save_file=False, show_result=False, load_imagePath=paths[0])
    elif OCR_model_type == "obj":
        return get_num_obj(save_file=False, show_result=False, load_imagePath=paths[0])
    elif OCR_model_type == "cls":
        return get_num_cls(
            save_file=False, show_result=False, load_imagePath=paths[0], allow_Null=True
        )
