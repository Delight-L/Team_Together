"""파트 3. 시각화 모음: 그래프 모양은 이 파일에서 바꾸세요.

각 함수는 데이터를 받아 Plotly 그림(fig)을 반환합니다.
main.py의 st.plotly_chart(fig)가 그 그림을 화면에 보여 줍니다.
"""

import re

import plotly.express as px
import plotly.graph_objects as go

from dashboard.settings import FACTORS, FACTOR_COLORS, THRESHOLDS
from dashboard.legacy_data import LEVEL_COLORS


def finish_chart(fig, height=340):
    # 모든 그래프에 공통으로 적용할 크기, 여백, 글꼴입니다.
    fig.update_layout(
        height=height,
        margin=dict(l=12, r=12, t=25, b=12),
        font=dict(family="Malgun Gothic, sans-serif"),
        legend=dict(orientation="h", y=-0.18),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def make_map_chart(rows, geometry, selected, band="전체", zoom=False):
    # 원본의 단순화된 행정동 경계를 재사용합니다.
    # 다른 지도로 교체하려면 이 함수만 GeoJSON/지도 라이브러리로 바꾸세요.
    # SVG의 M,L,Z 좌표를 Plotly의 채워진 다각형으로 변환합니다.
    fig = go.Figure()
    indexed = rows.set_index("district")
    for unit in geometry["units"]:
        if unit["n"] not in indexed.index:
            continue
        row = indexed.loc[unit["n"]]
        # 한 동에 여러 섬/다각형이 있어도 M 단위로 각각 그립니다.
        for segment in re.findall(r"M[^M]+", unit["d"]):
            coords = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", segment)]
            x, y = coords[::2], coords[1::2]
            if len(x) < 3 or len(x) != len(y):
                continue
            fig.add_trace(
                go.Scatter(
                    x=x + [x[0]],
                    y=y + [y[0]],
                    mode="lines",
                    fill="toself",
                    fillcolor=LEVEL_COLORS[row["level"]],
                    opacity=1 if band == "전체" or row["level"] == band else 0.18,
                    line=dict(
                        color="#132A3E" if unit["n"] == selected else "white",
                        width=3 if unit["n"] == selected else 1,
                    ),
                    text=f"{unit['n']} · {row['level']} · {row['score']:.1f}점",
                    hoverinfo="text",
                    hoveron="fills",
                    showlegend=False,
                )
            )
        if unit["a"] >= 3300 or unit["n"] == selected or zoom:
            fig.add_annotation(
                x=unit["cx"],
                y=unit["cy"],
                text=unit["n"],
                showarrow=False,
                font=dict(size=11, color="#172B3A"),
                bgcolor="rgba(255,255,255,0.7)",
            )
    x_range, y_range = [0, geometry["w"]], [geometry["h"], 0]
    small = [u for u in geometry["units"] if u["a"] < 3300]
    if zoom and len(small) >= 6:
        x_range = [min(u["cx"] for u in small) - 34, max(u["cx"] for u in small) + 34]
        y_range = [max(u["cy"] for u in small) + 34, min(u["cy"] for u in small) - 34]
    fig.update_xaxes(visible=False, range=x_range)
    fig.update_yaxes(visible=False, range=y_range, scaleanchor="x", scaleratio=1)
    fig.update_layout(dragmode="pan")
    return finish_chart(fig, 510)


def make_factor_chart(row, weights, kind="가로 막대"):
    total = sum(weights.values())
    names = [f"{label} ({weights[key]/total:.0%})" for key, label in FACTORS.items()]
    values = [row[key] for key in FACTORS]
    if kind == "레이더":
        # 그래프 종류 변경 예시 1: 같은 데이터를 레이더 차트로 표현합니다.
        fig = go.Figure(
            go.Scatterpolar(
                r=values + values[:1],
                theta=names + names[:1],
                fill="toself",
                line_color="#1F6F8B",
            )
        )
        fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100])))
    else:
        # x: 요인 점수, y: 요인 이름, orientation='h': 가로 막대
        fig = go.Figure(
            go.Bar(
                x=values,
                y=names,
                orientation="h",
                marker_color=FACTOR_COLORS,
                text=[f"{v:.1f}" for v in values],
                textposition="auto",
            )
        )
        fig.update_xaxes(range=[0, 100], title="요인 점수")
        fig.update_yaxes(autorange="reversed")
    return finish_chart(fig, 290)


def make_trend_chart(trend, kind="꺾은선"):
    # 그래프 종류 변경 예시 2: px.line → px.area / px.bar
    draw = {"꺾은선": px.line, "영역": px.area, "막대": px.bar}[kind]
    fig = draw(
        trend,
        x="period",
        y=list(trend.columns[1:]),
        color_discrete_sequence=["#8495A5", "#1F6F8B"],
        labels={"period": "기간", "value": "위험도", "variable": "지역"},
    )
    if kind == "막대":
        fig.update_layout(barmode="group")
    if kind == "영역":
        # 비교 시계열은 누적하면 점수가 더해지므로 겹치는 영역으로 표시합니다.
        fig.update_traces(stackgroup=None, fill="tozeroy", opacity=0.5)
    for threshold, label in zip(THRESHOLDS[1:], ["위험", "심각"]):
        fig.add_hline(
            y=threshold,
            line_dash="dot",
            line_color=LEVEL_COLORS[label],
            annotation_text=f"{label} {threshold}",
        )
    fig.update_yaxes(range=[0, 100])
    return finish_chart(fig)


def make_rank_chart(rows):
    top = rows.head(8).sort_values("score")
    fig = px.bar(
        top,
        x="score",
        y="district",
        color="level",
        orientation="h",
        color_discrete_map=LEVEL_COLORS,
        text="score",
        labels={"score": "위험도", "district": "행정동", "level": "단계"},
    )
    fig.update_traces(texttemplate="%{text:.1f}")
    fig.update_yaxes(categoryorder="array", categoryarray=top["district"].tolist())
    fig.update_xaxes(range=[0, 100])
    return finish_chart(fig)


def make_contribution_chart(rows, weights):
    # 원본의 요인별 기여도를 누적 막대로 나타냅니다.
    # 막대 전체 길이 = 위험도, 각 색의 길이 = 해당 요인의 가중 점수입니다.
    fig = go.Figure()
    total = sum(weights.values())
    for (key, label), color in zip(FACTORS.items(), FACTOR_COLORS):
        fig.add_bar(
            name=label,
            x=rows["district"],
            y=rows[key] * weights[key] / total,
            marker_color=color,
        )
    fig.update_layout(barmode="stack", yaxis_title="위험도 기여 점수")
    return finish_chart(fig, 400)
