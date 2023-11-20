# cafe_id만 입력하면 seat_id별로 한번에 나오는 코드
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import datetime
import logging
from collections import defaultdict

app = Flask(__name__)
CORS(app)
app.config['JSON_AS_ASCII'] = False

# Database connection parameters (replace with your database details)
db_params = {
    'host': '61.252.59.28',
    'port': '5432',
    'database': 'korenvm3',
    'user': 'korenvm3',
    'password': 'korenvm3',
    'client_encoding': 'utf8'
}



# Dictionary to store the last 10 seat_label values for each cafe_id and seat_id combination
last_10_seat_labels = {}

# Dictionary to store the last time and label for each cafe_id and seat_id combination
last_time_and_label = {}


cursor = None
conn = psycopg2.connect(**db_params)
cursor = conn.cursor()

# cafe_id, seat_id에 따른 정보 반환
def retrieve_seat_info(cafe_id, seat_id):
    global cursor  # Access the global cursor variable

    if cursor is None:
        conn = psycopg2.connect(**db_params)

        # Create a cursor
        cursor = conn.cursor()

    # SQL query to retrieve seat_x and seat_y for the specified cafe_id and seat_id
    query = f"""
    SELECT CAST(seat_x AS INTEGER), CAST(seat_y AS INTEGER)
    FROM cafeseatinfo
    WHERE cafe_id = {cafe_id} AND seat_id = {seat_id}
    """

    cursor.execute(query)
    seat_info = cursor.fetchone()

    return seat_info


# Function to retrieve the maximum of the last 10 seat_label values from the seatlabel table (안 써도 됨)
def retrieve_max_last_10_seat_labels(cafe_id, seat_id):
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    # SQL query to retrieve the maximum of the last 10 seat_label values for the specified cafe_id and seat_id
    query = f"""
    SELECT seat_label
    FROM seatlabel
    WHERE cafe_id = {cafe_id} AND seat_id = {seat_id}
    ORDER BY timestamp DESC
    LIMIT 10
    """

    cursor.execute(query)
    last_10_seat_labels_values = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    # Calculate the maximum value from the last 10 seat_label values
    max_last_10_seat_label = max(last_10_seat_labels_values) if last_10_seat_labels_values else None

    return max_last_10_seat_label


time_dict = {}  # Initialize time_dict outside the loop

# 데이터 받아오는 함수
def execute_query(query, params=None):
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)

    data = cursor.fetchall()
    conn.close()
    return data

import psycopg2

def execute_update_query(query, params=None):
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        conn.commit()  # Commit the transaction
    except psycopg2.Error as e:
        conn.rollback()  # Rollback the transaction in case of an error
        print(f"Error: {e}")
    finally:
        cursor.close()
        conn.close()


#
@app.route('/seatinfo/<int:cafe_id>/<int:seat_id>', methods=['GET'])
def get_seat_info_for_cafe_and_seat(cafe_id, seat_id):
    try:
        # 좌석 정보 (seat_x, seat_y, 등) 검색
        seat_info_query = "SELECT seat_id, seat_x, seat_y, etc, has_outlet, is_window_seat, capacity FROM cafeseatinfo WHERE cafe_id = %s AND seat_id = %s"
        seat_info = execute_query(seat_info_query, (cafe_id, seat_id))

        if not seat_info:
            return jsonify({"message": f"해당 Cafe ID {cafe_id} 및 Seat ID {seat_id}에 대한 좌석 정보를 찾을 수 없습니다."}), 404

        result = []

        for s_id, seat_x, seat_y, etc, has_outlet, is_window_seat, capacity in seat_info:
            # 각 seat_id에 대한 seat_label과 timestamp 검색 후 내림차순 정렬
            seat_label_query = "SELECT seat_label, timestamp FROM seatlabel WHERE cafe_id = %s AND seat_id = %s ORDER BY timestamp DESC"

            seat_label_data = execute_query(seat_label_query, (cafe_id, seat_id))

            seat_label = "2"
            time = 0
            timestamp_tmp = None
            first_seat_label = "2"

            for idx, (seat_label_value, timestamp) in enumerate(seat_label_data):
                if idx == 0:
                    first_seat_label = seat_label_value

                seat_label = seat_label_value

                if seat_label == "0" or seat_label == "1":  # 사람이 있을 때
                    if timestamp_tmp is None:
                        timestamp_tmp = timestamp
                    if s_id not in time_dict:
                        time_dict[s_id] = 0  # 각 seat_id마다 time을 정수로 초기화
                    time = time_dict[s_id]

                elif seat_label == "2":  # 아무도 없을 때
                    if timestamp_tmp is None:
                        timestamp_tmp = seat_label_data[-1][1]
                        break

                    if timestamp_tmp is not None:
                        time_difference = (timestamp_tmp - timestamp).total_seconds()
                        timestamp_tmp = None
                        time_dict[s_id] = int(time_difference / 60)  # Convert seconds to minutes and store in time_dict
                        break

            result.append({
                "seat_id": s_id,
                "seat_x": seat_x,
                "seat_y": seat_y,
                "etc": etc,
                "has_outlet": has_outlet,
                "is_window_seat": is_window_seat,
                "capacity": capacity,
                "time": time_dict.get(s_id, 0),  # 사전에서 해당 seat_id에 대한 time 값을 가져오기
                "seat_label": first_seat_label
            })

        result = sorted(result, key=lambda x: x["seat_id"])
        if result:
            return jsonify(result)
        else:
            return jsonify({"message": f"Cafe ID {cafe_id}에 대한 좌석 정보를 찾을 수 없습니다."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#카페 별 좌석 정보 반환
@app.route('/seatinfo/<int:cafe_id>', methods=['GET'])
def get_seat_info_for_cafe(cafe_id):
    try:
        # 요청된 카페 ID에 대한 좌석 정보 (seat_x, seat_y, 등) 검색
        seat_info_query = "SELECT seat_id, seat_x, seat_y, etc, has_outlet, is_window_seat, capacity FROM cafeseatinfo WHERE cafe_id = %s"
        seat_info = execute_query(seat_info_query, (cafe_id,))

        result = []

        for s_id, seat_x, seat_y, etc, has_outlet, is_window_seat, capacity in seat_info:
            # 각 seat_id에 대한 seat_label과 timestamp 검색
            seat_label_query = "SELECT seat_label, timestamp FROM seatlabel WHERE cafe_id = %s AND seat_id = %s ORDER BY timestamp DESC"
            seat_label_data = execute_query(seat_label_query, (cafe_id, s_id))

            person_query = "SELECT person FROM seatlabel WHERE cafe_id = %s AND seat_id = %s ORDER BY timestamp DESC"
            person_data = execute_query(person_query, (cafe_id, s_id))

            seat_label = "2"
            time = 0
            timestamp_tmp = None
            first_seat_label = "2"
            person = 0  # 기본값 설정

            for idx, (seat_label_value, timestamp) in enumerate(seat_label_data):
                print('!')
                if idx == 0:
                    first_seat_label = seat_label_value

                seat_label = seat_label_value

                if seat_label == "0" or seat_label == "1":  # 사람이 있을 때
                    if timestamp_tmp is None:
                        timestamp_tmp = timestamp
                    if s_id not in time_dict:
                        time_dict[s_id] = 0  # 각 seat_id마다 time을 정수로 초기화
                    time = time_dict[s_id]

                elif seat_label == "2":  # 아무도 없을 때
                    if timestamp_tmp is None:
                        timestamp_tmp = seat_label_data[-1][1]
                        break

                    if timestamp_tmp is not None:
                        time_difference = (timestamp_tmp - timestamp).total_seconds()
                        timestamp_tmp = None
                        time_dict[s_id] = int(time_difference / 60)  # Convert seconds to minutes and store in time_dict
                        break

            if idx <= len(person_data):
                person = person_data[0][0]

            result.append({
                "seat_id": s_id,
                "seat_x": seat_x,
                "seat_y": seat_y,
                "etc": etc,
                "has_outlet": has_outlet,
                "is_window_seat": is_window_seat,
                "capacity": capacity,
                "time": time_dict.get(s_id, 0),
                "seat_label": first_seat_label,
                "person": person
            })

        result = sorted(result, key=lambda x: x["seat_id"])
        if result:
            return jsonify(result)
        else:
            return jsonify({"message": f"Cafe ID {cafe_id}에 대한 좌석 정보를 찾을 수 없습니다."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500



#카페 별 평균 체류시간 계산
def calculate_average_stay_time(cafe_id):
    time_list_dict = {}

    try:
        # 요청된 카페 ID에 대한 좌석 정보 검색
        seat_info_query = "SELECT seat_id FROM cafeseatinfo WHERE cafe_id = %s"
        seat_info = execute_query(seat_info_query, (cafe_id,))

        for (s_id,) in seat_info:
            # 각 seat_id에 대한 seat_label과 timestamp 검색 후 내림차순 정렬
            seat_label_query = "SELECT seat_label, timestamp FROM seatlabel WHERE cafe_id = %s AND seat_id = %s ORDER BY timestamp DESC"
            seat_label_data = execute_query(seat_label_query, (cafe_id, s_id))

            timestamp_tmp = None

            for seat_label_value, timestamp in seat_label_data:
                if seat_label_value == "0" or seat_label_value == "1":  # 사람이 있을 때
                    if timestamp_tmp is None:
                        timestamp_tmp = timestamp

                elif seat_label_value == "2":  # 아무도 없을 때
                    if timestamp_tmp is not None:
                        time_difference = (timestamp_tmp - timestamp).total_seconds()
                        if s_id not in time_list_dict:
                            time_list_dict[s_id] = []
                        time_list_dict[s_id].append(int(time_difference / 60))  # Add time to the list
                        timestamp_tmp = None

        average_times = {}

        for (s_id,) in seat_info:
            if s_id not in time_list_dict:
                time_list_dict[s_id] = [0]  # 시간 차이가 없는 경우에 0 추가

        for s_id, times in time_list_dict.items():
            if times:
                average_times[s_id] = round(sum(times) / len(times), 2)
            else:
                average_times[s_id] = 0.00

        return {key: "{:.2f}".format(value) for key, value in average_times.items()}

    except Exception as e:
        print(f"Error: {str(e)}")
        return None

@app.route('/average_stay_time/<int:cafe_id>', methods=['GET'])
def get_average_stay_time(cafe_id):
    try:
        avg_times = calculate_average_stay_time(cafe_id)
        return jsonify(avg_times)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

#카페 테이블 별 평균 인원수 계산
@app.route('/average_person_per_seat/<int:cafe_id>', methods=['GET'])
def get_average_person_per_seat(cafe_id):
    try:
        # 요청된 카페 ID에 대한 좌석 정보 검색
        seat_info_query = "SELECT seat_id FROM cafeseatinfo WHERE cafe_id = %s"
        seat_info = execute_query(seat_info_query, (cafe_id,))

        person_avg_dict = {}

        for (s_id,) in seat_info:
            # 각 seat_id에 대한 seat_label과 person값 검색
            person_query = "SELECT person FROM seatlabel WHERE cafe_id = %s AND seat_id = %s AND (seat_label = '0' OR seat_label = '1')"
            person_data = execute_query(person_query, (cafe_id, s_id))

            if person_data:
                average_person = sum([person[0] for person in person_data]) / len(person_data)
                person_avg_dict[s_id] = round(average_person, 1)
            else:
                person_avg_dict[s_id] = 0.0

        return jsonify(person_avg_dict)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 전체 카페 정보 반환
@app.route('/cafe_info', methods=['GET'])
def get_all_cafes():
    query = "SELECT * FROM cafe"
    cafes = execute_query(query)

    if cafes:
        cafe_list = []
        for cafe in cafes:
            cafe_info = [
                cafe[0],  # cafe_id
                cafe[1],  # cafe_name
                cafe[2],  # cafe_location
                cafe[3],  # cafe_totalseats
                cafe[4],  # latitude
                cafe[5]   # longitude

            ]
            cafe_list.append(cafe_info)
        return jsonify(cafe_list), 200, {'Content-Type': 'application/json; charset=utf-8'}
    else:
        return jsonify({'message': 'No cafes found'})


# 카페 아이디에 따라 카페 정보 반환
@app.route('/cafe_info/<int:cafe_id>', methods=['GET'])
def get_cafe_by_id(cafe_id):
    query = "SELECT * FROM cafe WHERE cafe_id = %s"
    cafe = execute_query(query, (cafe_id,))
    if cafe:
        cafe_list1 = []
        cafe_info = [
            cafe[0][0],  # cafe_id
            cafe[0][1],  # cafe_name
            cafe[0][2],  # cafe_location
            cafe[0][3],  # cafe_totalseats
            cafe[0][4],  # latitude
            cafe[0][5],   # longitude
            cafe[0][6]

        ]
        cafe_list1.append(cafe_info)

        return jsonify(cafe_list1), 200, {'Content-Type': 'application/json; charset=utf-8'}
    else:
        return jsonify({'message': f'Cafe with ID {cafe_id} not found'})


# 각 카페에 있는 전체 좌석 반환 함수
def retrieve_seat_ids(cafe_id):
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    # SQL query to retrieve all seat_ids associated with the cafe_id
    query = f"""
    SELECT DISTINCT seat_id
    FROM cafeseatinfo
    WHERE cafe_id = {cafe_id}
    """

    cursor.execute(query)
    seat_ids = [row[0] for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return seat_ids
 
#대소문자 구별해서 카페 리스트 검색
@app.route('/cafe_search', methods=['GET'])
def get_cafes_by_name():
    try:
        search_string = request.args.get('cafe_search')

        if search_string is None:
            return jsonify({"error": "Missing search_string parameter in the request."}), 400

        # SQL 쿼리: cafe_name에서 문자열을 포함하는 모든 행을 선택
        query = """
        SELECT *
        FROM cafe
        WHERE cafe_name LIKE %s
        """
        
        # '%'를 사용하여 검색 문자열을 포함하는 모든 행을 찾습니다.
        search_string = f"%{search_string}%"

        cursor.execute(query, (search_string,))
        cafes = cursor.fetchall()
        conn.close()

        if cafes:
            # 검색 결과를 리스트로 변환하여 반환
            cafe_list = [dict(enumerate(cafe)) for cafe in cafes]
            return jsonify(cafe_list)
        else:
            return jsonify({"message": "No cafes found matching the search criteria."})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# userID에 따라 패스워드 데이터 반환 (web)
@app.route('/user_web/<string:user_id>', methods=['GET'])
def get_user_data_web(user_id):
    try:
        # Search the database for user_pw and manage_cafe_id data corresponding to the user ID (user_id)
        query = "SELECT user_pw, manage_cafe_id FROM user_web WHERE user_id = %s"
        user_data = execute_query(query, (user_id,))

        if user_data:
            user_pw, manage_cafe_id = user_data[0]  # Extract user_pw and manage_cafe_id from the query result
            return jsonify({"user_pw": user_pw, "manage_cafe_id": manage_cafe_id})
        else:
            return jsonify({"False"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# userID에 따라 패스워드, 이름 반환 (app)
@app.route('/user_app/<string:user_id>', methods=['GET'])
def get_user_data_app(user_id):
    try:
        # Search the database for user_id, user_pw, and user_name data corresponding to the user ID (user_id)
        query = "SELECT user_id, user_pw, user_name FROM user_app WHERE user_id = %s"
        user_data = execute_query(query, (user_id,))

        if user_data:
            user_id, user_pw, user_name = user_data[0]  # Extract user_id, user_pw, and user_name from the query result
            return jsonify({"user_id": user_id, "user_pw": user_pw, "user_name": user_name})
        else:
            return jsonify({"message": f"There is no data corresponding to user ID {user_id}."}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500



# 좌상단 우하단 위치 기준으로 카페 검색 결과 반환
@app.route('/search_cafes_within_bounds', methods=['GET'])
def search_cafes_within_bounds():
    word = request.args.get('query')
    upper_left_latitude = float(request.args.get('upper_left_latitude'))
    upper_left_longitude = float(request.args.get('upper_left_longitude'))
    lower_right_latitude = float(request.args.get('lower_right_latitude'))
    lower_right_longitude = float(request.args.get('lower_right_longitude'))

    try:
        query = """
            SELECT *
            FROM cafe
            WHERE latitude BETWEEN %s AND %s
              AND longitude BETWEEN %s AND %s
        """

        # make tuple to send param
        params = [lower_right_latitude, upper_left_latitude, upper_left_longitude, lower_right_longitude]

        if word:
            query += "AND cafe_name ILIKE %s"
            params.append('%' + word + '%')

        print(query, params)

        cafes = execute_query(query, params)

        result = []
        if cafes:
            for cafe in cafes:
                cafe_info = [
                    cafe[0],  # cafe_id
                    cafe[1],  # cafe_name
                    cafe[2],  # cafe_location
                    cafe[3],  # latitude
                    cafe[4],  # longitude
                    int(cafe[5]),  # cafe_currentseats
                    int(cafe[6])   # cafe_totalseats
                ]
                result.append(cafe_info)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#현재 카페 좌석별 인원 수 출력
@app.route('/latest_person_count/<int:cafe_id>', methods=['GET'])
def get_latest_person_count(cafe_id):
    try:
        # 모든 seat_id와 그에 해당하는 최신 timestamp의 person 값을 가져오는 SQL 쿼리
        query = """
        SELECT csi.seat_id, COALESCE(sl.person, 0) as person
        FROM cafeseatinfo csi
        LEFT JOIN (
            SELECT seat_id, person
            FROM seatlabel 
            WHERE cafe_id = %s AND timestamp = (
                SELECT MAX(timestamp) 
                FROM seatlabel 
                WHERE cafe_id = %s AND seatlabel.seat_id = seat_id
            )
        ) sl ON csi.seat_id = sl.seat_id
        WHERE csi.cafe_id = %s
        ORDER BY csi.seat_id;
        """
        
        results = execute_query(query, (cafe_id, cafe_id, cafe_id))
        
        # 결과를 JSON 형태로 변환
        output = [{"seat_id": seat_id, "person": person} for seat_id, person in results]

        return jsonify(output)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

#판매된 메뉴 1~4순위
@app.route('/sold_menu/<int:cafe_id>', methods=['GET'])
def get_cafe_sales(cafe_id):
    try:
        # Step 1: Retrieve menu_id and total_quantity_sold for the specified cafe_id from menusales table
        menu_sales_query = """
        SELECT ms.menu_id, SUM(ms.quantity_sold) AS total_quantity_sold
        FROM menusales ms
        WHERE ms.cafe_id = %s
        GROUP BY ms.menu_id
        ORDER BY total_quantity_sold DESC
        LIMIT 4
        """
        cursor.execute(menu_sales_query, (cafe_id,))
        menu_sales_data = cursor.fetchall()

        # Initialize a list to store menu data
        menu_data = []

        # Define the rank names
        rank_names = ["First", "Second", "Third", "Fourth"]

        # Step 2: Retrieve the menu_name for each of the most sold menu_ids
        for idx, (menu_id, total_quantity_sold) in enumerate(menu_sales_data):
            menu_name_query = """
            SELECT menu_name
            FROM cafemenu
            WHERE cafe_id = %s AND menu_id = %s
            """
            cursor.execute(menu_name_query, (cafe_id, menu_id))
            menu_name = cursor.fetchone()

            if menu_name:
                menu_data.append({
                    "Rank": rank_names[idx],  # Assign rank names here
                    "menu_name": menu_name[0],
                    "total_quantity_sold": total_quantity_sold
                })

        return jsonify({"cafe_id": cafe_id, "menu_data": menu_data})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



 #카페 총매출 반환
@app.route('/sales/<int:cafe_id>', methods=['GET'])
def get_cafe_total_sales(cafe_id):
    try:
        # Similar code as above for calculating total sales
        menu_sales_query = """
        SELECT menu_id, quantity_sold
        FROM menusales
        WHERE cafe_id = %s
        """
        cursor.execute(menu_sales_query, (cafe_id,))
        menu_sales_data = cursor.fetchall()

        total_sales = 0  # Initialize total sales to 0

        for menu_id, quantity_sold in menu_sales_data:
            menu_info_query = """
            SELECT menu_price
            FROM cafemenu
            WHERE cafe_id = %s AND menu_id = %s
            """
            cursor.execute(menu_info_query, (cafe_id, menu_id))
            menu_info = cursor.fetchone()

            if menu_info is not None:  # 결과가 None이 아닌 경우에만 처리
                menu_price = menu_info[0]
                total_sales += (menu_price * quantity_sold)

        return jsonify({"cafe_id": cafe_id, "total_sales": total_sales})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


       
#카페 월 별 매출 반환    
@app.route('/sales_month/<int:cafe_id>', methods=['GET'])
def get_cafe_monthly_sales(cafe_id):
    try:
        # Initialize a dictionary to store monthly sales with 0 as default
        monthly_sales = {str(month): 0 for month in range(1, 13)}

        # Query for fetching menu sales for a specific cafe
        menu_sales_query = """
        SELECT EXTRACT(MONTH FROM sale_timestamp) AS month, SUM(menu_price * quantity_sold) AS monthly_total
        FROM menusales
        JOIN cafemenu ON menusales.menu_id = cafemenu.menu_id
        WHERE cafemenu.cafe_id = %s
        GROUP BY month
        """
        cursor.execute(menu_sales_query, (cafe_id,))
        menu_sales_data = cursor.fetchall()

        # Update the monthly_sales dictionary with actual data
        for month, total_sales in menu_sales_data:
            monthly_sales[str(int(month))] = total_sales

        return jsonify({"cafe_id": cafe_id, "monthly_sales": monthly_sales})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#user_mark 즐겨찾기 정보 반환 
@app.route('/user_app_mark/<string:user_id>', methods=['GET'])
def get_user_marks(user_id):
    try:
        # Search the database for all 'user_mark' data corresponding to the user ID (user_id)
        query = "SELECT user_mark FROM user_app_mark WHERE user_id = %s"
        marks_data = execute_query(query, (user_id,))

        if marks_data:
            # Extract 'user_mark' values from the query result
            user_marks = [mark[0] for mark in marks_data]
            return jsonify({"success": user_marks})
        else:
            return jsonify({"fail": [0]}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#즐겨찾기 row 제거 함수
@app.route('/remove_user_mark', methods=['POST'])
def remove_user_mark():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        user_mark = data.get('user_mark')

        if user_id is None or user_mark is None:
            return jsonify({"error": "Missing user_id or user_mark in the request."}), 400

        # Delete the row with the specified user_id and user_mark
        delete_query = """
        DELETE FROM user_app_mark
        WHERE user_id = %s AND user_mark = %s
        """
        execute_update_query(delete_query, (user_id, user_mark))

        return jsonify({"message": "User mark removed successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#mark_update
@app.route('/update_mark', methods=['POST'])
def update_mark():
    try:
        # Get user_id and user_mark from the request JSON
        user_id = request.json.get('user_id')
        user_mark = request.json.get('user_mark')

        if not user_id or user_mark is None:
            return jsonify({"error": "Missing 'user_id' or 'user_mark' in the request JSON."}), 400

        # Insert a new record into the "user_app_mark" table
        insert_query = "INSERT INTO user_app_mark (user_id, user_mark) VALUES (%s, %s)"
        execute_update_query(insert_query, (user_id, user_mark))

        return jsonify({"message": "user_mark data added successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



#etc_update
@app.route('/update_etc/<int:cafe_id>/<int:seat_id>', methods=['PUT'])
def update_etc(cafe_id, seat_id):
    try:
        # Update the "etc" column in the "cafeseatinfo" table
        etc_data = request.json['etc']
        update_query = "UPDATE cafeseatinfo SET etc = %s WHERE cafe_id = %s AND seat_id = %s"
        execute_update_query(update_query, (etc_data,cafe_id, seat_id))

        return jsonify({"message": "etc data updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
#콘센트 유무 정보 업데이트
@app.route('/update_outlet/<int:cafe_id>/<int:seat_id>', methods=['PUT'])
def update_outlet(cafe_id, seat_id):
    try:
        # Update the "has_outlet" column in the "cafeseatinfo" table
        etc_data = request.json['has_outlet']
        update_query = "UPDATE cafeseatinfo SET has_outlet = %s WHERE cafe_id = %s AND seat_id = %s"
        execute_update_query(update_query, (etc_data,cafe_id, seat_id))

        return jsonify({"message": "has_outlet data updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

#좌석별 인원 수 정보 업데이트
@app.route('/update_capacity/<int:cafe_id>/<int:seat_id>', methods=['PUT'])
def update_capacity(cafe_id, seat_id):
    try:
        # Update the "capacity" column in the "cafeseatinfo" table
        etc_data = request.json['capacity']
        update_query = "UPDATE cafeseatinfo SET capacity = %s WHERE cafe_id = %s AND seat_id = %s"
        execute_update_query(update_query, (etc_data,cafe_id, seat_id))

        return jsonify({"message": "capacity data updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

#창가 여부 정보 업데이트
@app.route('/update_window/<int:cafe_id>/<int:seat_id>', methods=['PUT'])
def update_window(cafe_id, seat_id):
    try:
        # Update the "is_window_seat" column in the "cafeseatinfo" table
        etc_data = request.json['is_window_seat']
        update_query = "UPDATE cafeseatinfo SET is_window_seat = %s WHERE cafe_id = %s AND seat_id = %s"
        execute_update_query(update_query, (etc_data,cafe_id, seat_id))

        return jsonify({"message": "is_window_seat data updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500 


#user_id 중복인지 확인하는 코드
@app.route('/id_check/<string:user_id>', methods=['GET'])
def check_user_id(user_id):
    try:
        # Search the database to check if the user_id exists in the 'user_app' table
        query = "SELECT user_id FROM user_app WHERE user_id = %s"
        existing_user = execute_query(query, (user_id,))

        if existing_user:
            return jsonify({"message": "중복 id"}), 400
        else:
            return jsonify({"message": "사용 가능한 id"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#회원가입 (web)
@app.route('/join_web', methods=['PUT'])
def join_web():
    try:
        # Get user_id and user_pw from the request data
        user_id = request.json.get('user_id')
        user_pw = request.json.get('user_pw')

        if not user_id or not user_pw:
            return jsonify({"message": "user_id 또는 user_pw가 누락되었습니다."}), 400

        # Update user_id and user_pw in the 'user_web' table
        update_query = "UPDATE user_web SET user_pw = %s WHERE user_id = %s"
        execute_update_query(update_query, (user_pw, user_id))

        return jsonify({"message": "사용자 정보 업데이트 성공"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


#회원가입 (app) id, pw, name
@app.route('/join_app', methods=['PUT'])
def join_app():
    try:
        # Get user_id, user_pw, and user_name from the request data
        user_id = request.args.get('user_id')
        user_pw = request.args.get('user_pw')
        user_name = request.args.get('user_name')

        if not user_id or not user_pw or not user_name:
            print(1)
            return jsonify({"message": "user_id, user_pw, or user_name is missing."}), 400

        # Update the user_pw and user_name in the 'user_web' table
        update_query = "INSERT INTO user_app VALUES (%s, %s, %s)"
        execute_update_query(update_query, (user_id, user_pw, user_name))

        return jsonify({"message": "User information updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
