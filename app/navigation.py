import streamlit as st
import osmnx as ox
import networkx as nx
import pandas as pd
import math
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
import folium
from streamlit_folium import st_folium
import seaborn as sns

# -----------------------------
# 0. 페이지 설정
# -----------------------------
st.set_page_config(
    page_title="강남 출발 경로 분석",
    layout="wide"
)

# -----------------------------
# 사이드바 및 페이지 선택
# -----------------------------
st.sidebar.title("Navigation Dashboard")
page = st.sidebar.radio(
    "페이지 선택",
    ("홈", "지도 시각화", "KPI 분석", "ETA 분석", "상관분석/인사이트", "서비스 활용", "결론")
)

center_point = (37.4982, 127.0275)

@st.cache_data
def load_graph(center_point):
    return ox.graph_from_point(center_point, dist=20000, network_type="drive", simplify=True)

G = load_graph(center_point)

start = (37.4982, 127.0275)
destinations = {
    "Samseong": (37.5093, 127.0632),
    "Jamsil": (37.5134, 127.1000),
    "Pangyo": (37.3949, 127.1112),
    "Yeouido": (37.5218, 126.9240),
    "Gwanghwamun": (37.5718, 126.9765),
    "Seongsu": (37.5454, 127.0559),
    "Sadang": (37.4767, 126.9816),
    "Hanam": (37.5428, 127.2228),
}

@st.cache_data
def get_all_routes(_G, start, destinations):
    start_node = ox.distance.nearest_nodes(_G, start[1], start[0])

    nodes = {}
    routes = {}

    for name, (lat, lon) in destinations.items():
        end_node = ox.distance.nearest_nodes(_G, lon, lat)
        nodes[name] = end_node

        route = nx.shortest_path(_G, start_node, end_node, weight="length")
        routes[name] = route

    return start_node, nodes, routes

start_node, nodes, routes = get_all_routes(G, start, destinations)


# KPI 계산
@st.cache_data
def compute_kpi(_G, routes):
    results = []

    for name, route in routes.items():
        edges = ox.routing.route_to_gdf(_G, route)
        distance_km = edges["length"].sum() / 1000

        intersections = sum(1 for node in route if _G.degree[node] >= 3)
        intersection_density = intersections / distance_km if distance_km > 0 else 0

        left_turn = 0
        right_turn = 0

        for i in range(len(route)-2):
            node1, node2, node3 = route[i], route[i+1], route[i+2]

            x1, y1 = _G.nodes[node1]["x"], _G.nodes[node1]["y"]
            x2, y2 = _G.nodes[node2]["x"], _G.nodes[node2]["y"]
            x3, y3 = _G.nodes[node3]["x"], _G.nodes[node3]["y"]

            angle = math.degrees(
                math.atan2(y3 - y2, x3 - x2) -
                math.atan2(y1 - y2, x1 - x2)
            )

            if angle > 180: angle -= 360
            if angle < -180: angle += 360

            if angle > 30:
                left_turn += 1
            elif angle < -30:
                right_turn += 1

        turn_count = left_turn + right_turn

        results.append({
            "route": f"Gangnam → {name}",
            "distance_km": round(distance_km, 2),
            "intersections": intersections,
            "intersection_density": round(intersection_density,2),
            "turns": turn_count,
            "left_turns": left_turn,
            "right_turns": right_turn
        })

    df = pd.DataFrame(results)
    df["complexity_score"] = df["intersection_density"] + (df["turns"]*0.1)

    return df.sort_values("complexity_score", ascending=False)

df = compute_kpi(G, routes)

# ETA 시뮬레이션 계산
def estimate_eta(distance_km, intersections, left_turns, right_turns,
                 avg_speed_kmh=40,
                 intersection_delay_sec=5,
                 left_turn_delay_sec=8,
                 right_turn_delay_sec=3):
    travel_time_sec = (distance_km/avg_speed_kmh)*3600
    intersection_time_sec = intersections * intersection_delay_sec
    turn_time_sec = (left_turns*left_turn_delay_sec) + (right_turns*right_turn_delay_sec)
    eta_sec = travel_time_sec + intersection_time_sec + turn_time_sec
    return eta_sec/60

@st.cache_data
def add_eta(df):
    df = df.copy()

    df["eta_min"] = df.apply(lambda x: estimate_eta(
        x["distance_km"], 
        x["intersections"], 
        x["left_turns"], 
        x["right_turns"]
    ), axis=1)

    return df

df = add_eta(df)

# -----------------------------
# 페이지별 출력
# -----------------------------
if page == "홈":
    st.title("도로 구조 기반 KPI 및 ETA 분석")
    st.markdown("""
    **강남 출발 주요 경로의 도로 구조를 분석**하여  
    KPI 기반 ETA를 해석하고 서비스 활용 가능성을 탐색합니다.
    """)
    st.markdown("---")
    st.header("📌 목표")
    st.markdown("""
    - 도로 구조 KPI 정의 (교차로, 회전, 밀도 등)
    - KPI 기반 ETA 시뮬레이션
    - 서비스 활용 가능성 탐색
    """)

elif page == "지도 시각화":

    st.header("지도 기반 경로 시각화")
    st.markdown(""" 
    - 실제 내비 경로(시간 기준)와는 차이 있음
    - 도로 구조 비교 목적
    """)
    
    m = folium.Map(location=start, zoom_start=11)

    # 시작점
    folium.Marker(start, tooltip="Gangnam", icon=folium.Icon(color="black")).add_to(m)

    colors = ["red", "blue", "green", "purple", "orange", "darkred", "cadetblue", "black"]

    for i, (name, route) in enumerate(routes.items()):
        coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in route]

        folium.PolyLine(
            coords,
            color=colors[i],
            weight=5,
            opacity=0.8,
            tooltip=name
        ).add_to(m)

        end_coord = coords[-1]
        folium.Marker(end_coord, tooltip=name).add_to(m)

    st_folium(m, width=1000, height=700)
    

elif page == "KPI 분석":
    st.header("KPI 정의 및 계산")
    st.markdown("""  
    - **거리** (Distance)
    - **교차로 수** (degree ≥ 3)
    - **교차로 밀도** (Intersections / km)
    - **회전 수** (±30° 이상)
    - **복잡도 지수** = 밀도 + (회전 * 가중치)
    """)
    st.markdown("""
    ---
    KPI + ETA 결과 데이터
    """)
    st.dataframe(df)
    st.markdown("""---""")
    st.header("KPI 시각화")

    # KPI 리스트
    kpi_list = ["distance_km", "intersections", "intersection_density", "turns", "complexity_score"]

    # KPI 제목
    kpi_titles = {
        "distance_km":"Route Distance",
        "intersections":"Intersection Count",
        "intersection_density":"Intersection Density",
        "turns":"Turn Count",
        "complexity_score":"Route Complexity Score"
    }

    # KPI 설명 (추가)
    kpi_desc = {
        "distance_km": "경로의 총 이동 거리",
        "intersections": "경로 내 교차로 수 (degree ≥ 3)",
        "intersection_density": "km당 교차로 수",
        "turns": "방향 변화가 ±30° 이상인 회전 수",
        "complexity_score": "교차로 밀도와 회전 수를 결합한 경로 복잡도 지표"
    }

    # 👉 KPI 선택 UI (radio 추천)
    selected_kpi = st.radio("KPI 선택", kpi_list, horizontal=True)

    # 설명 표시
    st.markdown(f"**설명:** {kpi_desc[selected_kpi]}")

    # 그래프 생성
    fig, ax = plt.subplots()
    ax.set_title(kpi_titles[selected_kpi])
    ax.bar(df["route"], df[selected_kpi])
    ax.set_xlabel("Route")

    if selected_kpi == "distance_km":
        ax.set_ylabel("Distance (km)")
    elif selected_kpi == "intersection_density":
        ax.set_ylabel("Intersections per km")
    elif selected_kpi == "complexity_score":
        ax.set_ylabel("Complexity Score")
    else:
        ax.set_ylabel(kpi_titles[selected_kpi])

    plt.xticks(rotation=45)
    st.pyplot(fig)


    st.markdown("""---""")
    st.header("KPI 종합 해석")
    st.markdown("""
    각 경로는 거리뿐 아니라 교차로 밀도와 회전 구조 차이에 따라 서로 다른 주행 특성 나타남  
    **경로 유형 요약**  
    - 장거리 외곽 경로 (강남 → 하남)  
    → 거리와 회전 수가 모두 높아 복잡도 지수가 가장 높게 나타남  
    → 특히 거리 자체가 길기 때문에 ETA에 가장 큰 영향을 줄 가능성이 큼  
      
    - 도심 내부 이동 경로 (강남 → 성수, 사당)  
    → 교차로 밀도와 회전 수가 높은 편  
    → 신호 대기 및 방향 전환이 빈번하게 발생하는 특징  
      
    - 도심 중심 이동 경로 (강남 → 광화문, 여의도)  
    → 교차로 밀도는 중간 수준  
    → 구조적 복잡성과 거리 요소가 함께 작용하는 경로  
      
    - 일반 도심 이동 경로 (강남 → 잠실, 삼성)  
    → 잠실은 중간 수준의 도심 이동  
    → 삼성은 교차로 밀도가 높은 도심형 경로 특성을 일부 보임  

    - 간선도로 중심 경로 (강남 → 판교)  
    → 교차로 밀도가 가장 낮고 직선 비중이 높은 구조
    → 구조적으로 단순하고 일정한 속도로 주행 가능하여 주행 난이도 낮음
    """)

elif page == "ETA 분석":
    st.header("ETA 추정값 시각화")
    st.markdown("""
    - 본 ETA는 실제 교통 데이터를 활용한 예측 모델이 아닌  
    도로 구조 요소(거리, 교차로, 회전)가 시간에 미치는 영향을 설명하기 위한 시뮬레이션 모델  
      
    - 특히 좌회전/우회전/교차로 지연을 분리하여 반영함으로써  
    단순 거리 기반 모델 대비 **시간 구성 요소를 해석할 수 있는 구조**를 가짐  
    """)
    with st.expander("ETA 계산 함수 보기"):
        st.code("""
        def estimate_eta(distance_km, intersections, left_turns, right_turns,
                        avg_speed_kmh=40,
                        intersection_delay_sec=5,
                        left_turn_delay_sec=8,
                        right_turn_delay_sec=3):

            # 거리 기반 시간
            travel_time_sec = (distance_km / avg_speed_kmh) * 3600
            
            # 교차로 지연
            intersection_time_sec = intersections * intersection_delay_sec
            
            # 회전 지연 (좌/우 분리)
            turn_time_sec = (left_turns * left_turn_delay_sec) + \\
                            (right_turns * right_turn_delay_sec)
            
            eta_sec = travel_time_sec + intersection_time_sec + turn_time_sec
            
            return eta_sec / 60
        """, language="python")

    fig, ax = plt.subplots()
    ax.set_title("ETA by Route")
    ax.bar(df["route"], df["eta_min"])
    ax.set_ylabel("ETA (minutes)")
    plt.xticks(rotation=45)
    st.pyplot(fig)


elif page == "상관분석/인사이트":
    st.header("KPI와 ETA 관계 탐색")
    st.markdown("""
    📌 **분석 기준**

    - 산점도: 핵심 변수 (교차로 밀도, 회전 수)
    - 히트맵: 전체 KPI 관계
    """)

    fig, ax = plt.subplots()
    ax.scatter(df["intersection_density"], df["eta_min"])
    ax.set_xlabel("Intersection Density (per km)")
    ax.set_ylabel("ETA (minutes)")
    ax.set_title("Intersection Density vs ETA")
    st.pyplot(fig)

    st.markdown("""
    ✅ **교차로 밀도 vs ETA**  
      
    - 단순 선형 관계 아님  
    - ETA는 거리·회전 등 여러 영향 함께 작용  
      
    👉 **단일 KPI로 ETA 설명 어려움**  
    """)

    fig, ax = plt.subplots()
    ax.scatter(df["turns"], df["eta_min"])
    ax.set_xlabel("Turn Count")
    ax.set_ylabel("ETA (minutes)")
    ax.set_title("Turn Count vs ETA")
    st.pyplot(fig)

    st.markdown("""
    ✅ **회전 수 vs ETA**  
      
    - 회전 수 증가 시 ETA 증가 경향 일부 존재  
    - 동일 구간 내 분산 발생  
      
    👉 **독립 변수라기보다 복합 요소**  
    """)
    
    st.markdown("""
    💡 **핵심**  
      
    - ETA = 거리 + 구조 요소 결합  
    - KPI = 시간의 구성 요소 설명 역할  
      
    👉 단일 KPI로 ETA 설명에는 한계 존재 → 다변량 접근 필요
    """)

    st.markdown("---")
    st.header("KPI 영향도 분석")
    st.markdown("""
    📌 **주의사항**

    - 샘플 수 제한
    - 통계적 일반화 한계
    - 시뮬레이션 기반 결과

    👉 **탐색적 분석으로 해석 필요**
    """)

    corr = df.select_dtypes(include='number').corr()
    fig, ax = plt.subplots(figsize=(6,5))
    sns.heatmap(corr, 
    annot=True, 
    cmap="coolwarm", 
    fmt=".2f", 
    linewidths=0.5, 
    ax=ax)
    ax.set_title("Correlation between KPI and ETA")
    st.pyplot(fig) 

    st.markdown("""
    💡 **해석**
      
    - Distance: ETA와 가장 높은 상관  
    - Turns: ETA와 높은 상관관계가 나타났으나,  
    intersections 및 좌/우회전 수와 구조적으로 연관되어 있어 독립적인 영향으로 해석하기에는 한계 존재  
    - Density: 독립적 영향은 제한적  
    """)

    st.markdown("---")
    st.header("분석 인사이트")
    st.markdown("""
    도로 구조 KPI 분석 결과, ETA는 단순 거리뿐 아니라  
    다양한 도로 구조가 함께 반영된 값으로 나타남  

    이를 통해 **각 경로의 이동 시간이 어떤 구조적 요소로 구성되는지 해석 가능**  
      
    - **도심:** 복잡 (교차로·회전 많음)  
      
    - **외곽:** 단순하지만 거리 영향 큼   
      
    - **복잡도 지수:** 경로 간 구조적 차이를 정량적으로 비교 가능  
    """)

elif page == "서비스 활용":
    st.header("서비스 활용 가능성")
    st.markdown("""
    👉 기존 내비게이션이 시간 중심 최적화에 집중되어 있다면,  
    본 분석의 KPI는 사용자 경험(운전 난이도, 피로도)을 반영한 보조 지표로 활용 가능  
      
    이를 기반으로 다음과 같은 서비스 확장 가능
    """)
    st.markdown("""
    #### **1️⃣ 경로 추천 알고리즘 설계**  
      
    기존 내비게이션은 주로 **최단 거리 또는 최소 시간** 기준으로 경로를 추천  
    그러나 본 분석의 KPI를 활용할 경우, 다음과 같은 **다중 기준 경로 추천 전략** 설계 가능  
    
    - **Fast**  
    → ETA 최소화 기준  
      
    - **Simple**  
    → Complexity Score 최소화  
      
    - **Balanced**  
    → ETA + Complexity Score를 함께 고려한 혼합 최적화   
      
    예시)  
    `Route Score = ETA + α × Complexity Score`  
      
    👉 사용자 성향(초보 운전자, 출퇴근 사용자 등)에 따라 α 값을 조정하여 맞춤형 경로 추천  
      
    #### **2️⃣ ETA 보정 로직 설계**   
      
    기존 ETA는 거리 및 평균 속도 중심으로 계산되는 경우가 많으나,  
    본 분석의 KPI를 활용하면 **경로 구조 기반 보정 로직** 추가 가능   
      
    예시)  
    `ETA = Base Travel Time`  
    `+ (Intersection Count × Intersection Delay)`  
    `+ (Left Turn × Left Turn Delay)`  
    `+ (Right Turn × Right Turn Delay)`  
      
    👉 도심/간선도로 차이와 같은 **경로 특성별 ETA 정밀도 개선** 가능  
    
    #### **3️⃣ 경로 유형 기반 사용자 안내 기능**  
    
    - **Urban**: 교차로 밀도와 회전 수가 높은 도심 경로  
    - **Highway**: 직선 구간 비중이 높은 단순 경로  
    - **Mixed**: 도심과 간선도로가 혼합된 경로  
    """)

    density_q75 = df["intersection_density"].quantile(0.75)
    turn_q25 = df["turns"].quantile(0.25)

    def classify_route(row):
        if row["intersection_density"] >= density_q75:
            return "Urban"
        elif row["turns"] <= turn_q25:
            return "Highway"
        else:
            return "Mixed"

    df["route_type"] = df.apply(classify_route, axis=1)
    st.dataframe(df[["route", "route_type"]])

    st.markdown("""
    📌 **결과**
      
    - 대부분 Mixed
    - 서울 도로 구조 특성상 단순 기준 분류 한계
      
    👉 기준 개선 시 활용 가능  
      
    📌 **활용**

    - 경로 특성 안내  
    - 난이도 기반 추천  
    - 사용자 선택형 경로 제공  
    """)
      
    #### **4️⃣ 신규 서비스 기능 제안**  
    st.markdown("""  
    본 분석에서 도출된 Complexity Score는 다음과 같은  
    **신규 내비게이션 기능 설계에 활용 가능**  
      
    - **최소 회전 경로 옵션**  
    - **운전 난이도 기반 경로 추천**  
    - **Navigation Complexity Index (NCI)**  
    → 특정 지역 및 경로의 복잡도 변화 모니터링 지표로 활용  
    """)

    st.markdown("""
    👉 KPI → 경로 추천 + ETA + UX 개선 연결 가능한 서비스 설계 요소
    """)

    st.markdown("---")
    st.header("모니터링 KPI 제안")
    st.markdown("""
    **Navigation Complexity Index (NCI)**  
    - 정의: 경로 복잡도 지수 기반 서비스 모니터링 지표  
    - 목적: 사용자 주행 난이도 및 경로 안내 품질 모니터링  
      
    **활용**  
    - 특정 지역 복잡도 상승 감지
    - 경로 안내 난이도 증가 구간 탐지
    - 사용자 경험 저하 사전 대응
    """)


elif page == "결론":
    st.header("결론")
    st.markdown("""
    - ETA는 거리 영향이 가장 크지만,  
    동일 시간이라도 경로 구조에 따라 주행 난이도는 크게 달라질 수 있음   
      
    👉 본 분석은 단순 이동 시간 비교를 넘어  
    **ETA를 구성하는 구조적 요인을 해석할 수 있는 지표 체계를 구축했다는 데 의의**가 있음  
      
    이러한 접근은 내비게이션 서비스에서  
    - 경로 추천 알고리즘 개선 
    - ETA 보정 로직 설계  
    - 사용자 맞춤형 경로 안내  
      
    등에 활용될 수 있음
    """)
    
    st.markdown("---")
    st.header("한계")
    st.markdown("""
    본 분석은 구조 기반 시뮬레이션으로,  
    실제 서비스 적용 시에는 교통량, 신호 체계, 시간대별 속도 데이터 등 추가적 반영 필요  
      
    향후 실시간 교통 데이터를 결합할 경우, 보다 정밀한 ETA 모델링 가능
    """)