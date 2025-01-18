import datetime
import os
import sqlite3

def check_and_create_database(db_file):
    """
    检查数据库文件是否存在，如果不存在则创建数据库及相关的数据表（hub_info表和mold_info表）
    :param db_file: 数据库文件的路径
    :return:
    """
    # 获取数据库文件所在的目录路径
    db_dir = os.path.dirname(db_file)

    # 如果目录路径不存在，则创建目录
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    if not os.path.exists(db_file):
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()

        # 创建数据库中可能需要的其他表，这里先假设没有其他表，如有需要可按下面格式添加其他表的创建语句
        create_tables = [
            '''
            CREATE TABLE IF NOT EXISTS hub_info (
                hub_id INTEGER PRIMARY KEY AUTOINCREMENT,
                recognition_time TEXT,
                mold_number TEXT
            )
            ''',
            '''
            CREATE TABLE IF NOT EXISTS mold_info (
                mold_number TEXT PRIMARY KEY,
                mold_name TEXT
            )
            '''
        ]

        for create_table_sql in create_tables:
            cursor.execute(create_table_sql)

        conn.commit()
        conn.close()
        return '数据检查成功...'

def insert_hub_info(db_file, mold_number):
    """
    向轮毂信息表（hub_info）插入一条数据记录，其中识别时间会自动生成当前时间
    :param db_file: 数据库文件的路径，应与check_and_create_database函数中使用的数据库文件路径一致。
    :param mold_number: 要插入的模具编号，通常是通过OCR识别出来的，会同时插入到hub_info表和mold_info表（若mold_info表中不存在该编号）。
    """
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 先在mold_info表中添加mold_number（若不存在）
    cursor.execute("INSERT OR IGNORE INTO mold_info (mold_number) VALUES (?)", (mold_number,))

    cursor.execute("INSERT INTO hub_info (recognition_time, mold_number) VALUES (?,?)",
                   (current_time, mold_number))

    conn.commit()
    conn.close()

def query_hub_info_by_mold_number(db_file, mold_number):
    """
    查询轮毂信息表（hub_info）中的数据记录
    :param db_file: 数据库文件的路径，应与其他函数中使用的数据库文件路径一致。
    :param mold_number: 要查询的模具编号。

    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hub_info WHERE mold_number=?", (mold_number,))
    columns = [description[0] for description in cursor.description]
    results =  [columns] + cursor.fetchall()
    conn.close()
    return results

def query_mold_info_by_number(db_file, mold_number):
    """
        查询模具信息表（mold_info）中的数据记录
    :param db_file:  数据库文件的路径，应与其他函数中使用的数据库文件路径一致。
    :param mold_number: 要查询的模具编号。
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mold_info WHERE mold_number=?", (mold_number,))
    columns = [description[0] for description in cursor.description]
    result = [columns]+cursor.fetchone()
    conn.close()
    return result

def update_hub_info(db_file, hub_id, recognition_time=None, mold_number=None):
    """
    修改轮毂信息表（hub_info）中的数据记录
    :param db_file: 数据库文件的路径，应与其他函数中使用的数据库文件路径一致。
    :param hub_id:  要修改的轮毂记录的ID，通过该ID定位到要修改的具体记录。
    :param recognition_time: 可选的参数，要更新的识别时间值，如果为None则不更新该字段。
    :param mold_number: 可选的参数，要更新的模具编号值，如果为None则不更新该字段。
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    update_fields = []
    update_values = []

    if recognition_time is not None:
        update_fields.append("recognition_time =?")
        update_values.append(recognition_time)
    if mold_number is not None:
        update_fields.append("mold_number =?")
        update_values.append(mold_number)

    if update_fields:
        update_query = "UPDATE hub_info SET " + ", ".join(update_fields) + " WHERE hub_id =?"
        update_values.append(hub_id)
        cursor.execute(update_query, tuple(update_values))

    conn.commit()
    conn.close()

def update_mold_info(db_file, mold_number, mold_name=None):
    """
    修改模具信息表（mold_info）中的数据记录
    :param db_file: 数据库文件的路径，应与其他函数中使用的数据库文件路径一致。
    :param mold_number: 要删除的轮毂记录的ID，通过该ID定位到要删除的具体记录。
    :param mold_name: 要更新的模具名称值，如果为None则不更新该字段。
    :type db_file: str
    :type mold_number: str
    :type mold_name: str
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    update_fields = []
    update_values = []

    if mold_name is not None:
        update_fields.append("mold_name =?")
    update_values.append(mold_name)

    if update_fields:
        update_query = "UPDATE mold_info SET " + ", ".join(update_fields) + "WHERE mold_number =?"
        update_values.append(mold_number)
        cursor.execute(update_query, tuple(update_values))

    conn.commit()
    conn.close()

def delete_hub_info_by_id(db_file, hub_id):
    """
    根据轮毂ID删除轮毂信息表（hub_info）中的一条数据记录
    :param db_file: 数据库文件的路径，应与其他函数中使用的数据库文件路径一致。
    :param hub_id: 要删除的轮毂记录的ID，通过该ID定位到要删除的具体记录。
    :type db_file: str
    :type hub_id: str
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hub_info WHERE hub_id=?", (hub_id,))
    conn.commit()
    conn.close()

def delete_mold_info_by_number(db_file, mold_number):
    """
    根据模具编号删除模具信息表（mold_info）中的一条数据记录,如果不存在，则在mold_info表中执行删除操作，删除指定mold_number的记录。
    :param db_file: 数据库文件的路径，应与其他函数中使用的数据库文件路径一致。
    :param mold_number: 要删除的模具记录的编号，通过该编号定位到要删除的具体记录。

    :type db_file: str
    :type mold_number: str
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # 检查mold_number在hub_info表中是否存在
    cursor.execute("SELECT COUNT(*) FROM hub_info WHERE mold_number=?", (mold_number,))
    count = cursor.fetchone()[0]

    if count == 0:
        cursor.execute("DELETE FROM mold_info WHERE mold_number=?", (mold_number,))

    conn.commit()
    conn.close()

def query_hub_info_by_time_range(db_file, start_time, end_time):
    """
    筛选查询指定时间范围内的轮毂信息表（hub_info）中的数据记录
    :param db_file: 数据库文件的路径，应与其他函数中使用的数据库文件路径一致。
    :param start_time: 指定时间范围的开始时间，格式应为 'YYYY-MM-DD HH:MM:SS'
    :param end_time: 指定时间范围的结束时间，格式应为 'YYYY-MM-DD HH:MM:SS'
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hub_info WHERE recognition_time BETWEEN? AND?",
                   (start_time, end_time))
    columns = [description[0] for description in cursor.description]
    results = [columns]+cursor.fetchall()
    conn.close()
    return results

def execute_custom_sql(db_file, sql_command):
    """
    执行自定义SQL指令
    :param db_file: 数据库文件的路径，应与其他函数中使用的数据库文件路径一致。
    :param sql_command: 要执行的自定义SQL指令
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    try:
        cursor.execute(sql_command)
        if sql_command.strip().lower().startswith("select"):
            columns = [description[0] for description in cursor.description]
            results = [columns]+cursor.fetchall()
            conn.close()
            return results
        else:
            conn.commit()
            conn.close()
            return "操作成功执行"
    except sqlite3.Error as e:
        conn.close()
        return f"操作失败: {e}"

def query_all_hub_info(db_file):
    """
    查询轮毂信息表（hub_info）中的所有数据记录，返回所有轮毂的情况。

    :param db_file: 数据库文件的路径，应与其他函数中使用的数据库文件路径一致。
    :type db_file: str

    功能：
    1. 连接到数据库。
    2. 在hub_info表中执行查询操作，获取所有记录。
    3. 获取查询结果（可能是多条记录）并返回。
    4. 关闭数据库连接。
    """
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM hub_info")
    columns = [description[0] for description in cursor.description]
    results = [columns] + cursor.fetchall()
    conn.close()
    return results


