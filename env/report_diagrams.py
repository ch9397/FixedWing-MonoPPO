# matplotlib.rcParams['text.usetex'] = True
from matplotlib import rc
# rc('font',**{'family':'sans-serif','sans-serif':['Helvetica']})
## for Palatino and other serif fonts use:
# rc('font', **{'family': 'serif', 'serif': ['Computer Modern']})
# ('text', usetex=True)
import matplotlib.pyplot as plt
import env.jsbsim_properties as prp
import env.navigation as navigation
import math
import numpy as np


class ReportGraphs:
    def __init__(self, sim):
        self.sim = sim
        self.nav = navigation.LocalNavigation(sim)

        self.time = []

        self.lat_m = []
        self.long_m = []
        self.alt = []

        self.yaw = []
        self.pitch = []
        self.roll = []

        self.aileron_cmd = []
        self.elevator_cmd = []
        self.throttle_cmd = []
        self.rudder_cmd = []

        self.aileron_combined = []
        self.elevator = []
        self.throttle = []

        self.p = []
        self.q = []
        self.r = []

        self.airspeed = []
        self.vs = []

    def get_time_data(self):
        self.time.append(self.sim.get_time())

    def get_pos_data(self):
        self.lat_m.append(self.nav.get_local_pos()[0])
        self.long_m.append(self.nav.get_local_pos()[1])
        self.alt.append(self.sim.get_local_position()[2])

    def get_attitude_data(self):
        self.pitch.append(self.sim.get_local_orientation()[0] * (180 / math.pi))
        self.roll.append(self.sim.get_local_orientation()[1] * (180 / math.pi))
        self.yaw.append(self.sim.get_local_orientation()[2] * (180 / math.pi))

    def get_rate_data(self):
        self.p.append(self.sim[prp.p_radps])
        self.q.append(self.sim[prp.q_radps])
        self.r.append(self.sim[prp.r_radps])

    def get_airspeed(self):
        self.airspeed.append(self.sim[prp.airspeed] * 0.5925)

    def get_control_command(self):
        # 这个方法用于获取控制命令的数据。具体来说，它将飞行模拟器中的副翼（aileron_combined_rad）和升降舵（elevator）的弧度值转换为度数，并将其添加到相应的列表中（aileron_combined 和 elevator）
        self.aileron_combined.append(self.sim[prp.aileron_combined_rad] * (180.0 / math.pi))   # self.sim[prp.aileron_combined_rad] 获取模拟器中的副翼的弧度值。
        self.elevator.append(self.sim[prp.elevator] * (180.0 / math.pi))  # self.sim[prp.elevator] 获取模拟器中的升降舵的弧度值。
        # 将弧度值转换为度数：* (180.0 / math.pi)。
        # 将转换后的值分别添加到 aileron_combined 和 elevator 列表中。


    def get_graph_info(self):
        self.get_time_data()
        self.get_pos_data()
        self.get_attitude_data()
        self.get_rate_data()
        self.get_airspeed()
        self.get_control_command()

    def trace_plot(self, desired_points):  # trace_plot 函数用于创建一个轨迹图，显示了实际飞机轨迹和命令的航点
        fig, ax = plt.subplots()  # 创建一个新的图形和轴对象
    #    ax.set_title(r'\textbf{Plan View Track}')  # 设置轨迹图的标题为 'Plan View Track'，平面视图轨道。
        ax.set_title(r'Plan View Track')
        ax.set_xlabel(r'x position [$m$]')  # 设置 x 轴标签为 'x position [$m$]'。
        ax.set_ylabel(r'y position [$m$]')  # 设置 y 轴标签为 'y position [$m$]'。
        plt.grid(True)  # 显示网格线。
        points, = ax.plot([i[0] for i in desired_points], [i[1] for i in desired_points], marker='^',
                          color='#FF7F11', linestyle='None')  # 在轨迹图上绘制命令的航点，使用橙色三角形标记。
        line, = ax.plot(self.lat_m, self.long_m, linestyle='--', color='#0077B6')  # 在轨迹图上绘制实际轨迹，使用蓝色虚线。
        line.set_label(r'track made good')  # 设置实际轨迹的标签。
        points.set_label(r'commanded fly-by waypoints')  # 设置命令的航点的标签。
        ax.legend()  # 显示图例。
        ax.set_aspect('equal')  # 保持轴的纵横比相等。
        # plt.savefig('plots/trace_plot.eps')  # 将轨迹图保存为文件 "trace_plot.eps"。
        plt.savefig('plots/trace_plot')
        # plt.show()  #  显示轨迹图。


    def control_response(self, start_time, stop_time, update_frequency):
        # 这个函数生成的图表显示了随着时间的推移的滚转和俯仰响应，右侧的Y轴包含了副翼和副翼组合的额外信息。橙色用于虚线，蓝色用于实线。

        # 这个函数负责创建一个控制响应图，包含两个子图，一个用于滚转响应（Roll Response），另一个用于俯仰响应（Pitch Response）。
        # Roll Response (横滚响应)：在第一个子图中，绘制了时间范围内的横滚速率 q（虚线，橙色）和副翼角度 elevator（实线，蓝色）的图形。横轴表示时间，左侧纵轴表示横滚速率 q，右侧纵轴表示副翼角度 elevator。
        # 滚转响应子图（ax1）：
        start = start_time * update_frequency
        stop = stop_time * update_frequency
        orange = '#FF7F11'
        blue = '#0077B6'
        ax1 = plt.subplot(211)  # 创建第一个子图，用于滚转响应。211表示一个2x1的图表网格，这是第一个子图。
        # ax1.plot(self.time[start:stop], self.q[start:stop], linestyle='--', color=orange)
    #   ax1.set_title(r'\textbf{Roll Response}')
        ax1.set_title(r'Roll Response')  # 设置滚转响应子图的标题。
        ax1.set_xlabel(r'time[s]')  # 设置X轴标签，表示时间（秒）。
        ax1.set_ylabel(r'q')  #  设置左Y轴标签，表示滚转速率 q（滚转响应）。
        ax3 = ax1.twinx()  # 创建一个共享X轴的次坐标轴，用于在同一子图上绘制额外的数据，但使用不同的刻度（右Y轴）。
        ax3.plot(self.time[start:stop], self.elevator[start:stop], linestyle='-', color=blue)  # 在右Y轴上绘制副翼数据。

        # Pitch Response (俯仰响应)：在第二个子图中，绘制了时间范围内的俯仰速率 p（虚线，橙色）和副翼组合角度 aileron_combined（实线，蓝色）的图形。横轴表示时间，左侧纵轴表示俯仰速率 p，右侧纵轴表示副翼组合角度 aileron_combined。
        # 俯仰响应子图（ax2）：
        ax2 = plt.subplot(212)  # 创建第二个子图，用于俯仰响应。212表示一个2x1的图表网格，这是第二个子图
        # ax2.plot(self.time[start:stop], self.p[start:stop], linestyle='--', color=orange)
    #    ax2.set_title(r'\textbf{Pitch Response}')
        ax2.set_title(r'Pitch Response')  # 设置俯仰响应子图的标题。
        ax2.set_xlabel(r'time [s]')  # 设置X轴标签，表示时间（秒）。
        ax4 = ax2.twinx()  # 创建一个共享X轴的次坐标轴，用于在同一子图上绘制额外的数据，但使用不同的刻度（右Y轴）。
        ax4.plot(self.time[start:stop], self.aileron_combined[start:stop], linestyle='-', color=blue)  # 在右Y轴上绘制副翼组合数据。


        # ax5 = plt.subplot(212)
        # plt.plot(self.time[start:stop], self.yaw[start:stop], linestyle='--', color=orange)
        # ax5.set_title(r'\textbf{Pitch Response}')
        # ax5.set_xlabel(r'time [s]')
        # ax6 = ax2.twinx()
        # ax6.plot(self.time[start:stop], self.aileron_combined[start:stop], linestyle='-', color=blue)
        # plt.savefig('plots/Control_response.eps')
        plt.savefig('plots/Control_response')
        # plt.show()

    def three_d_plot(self, start_time, stop_time, update_frequency):
        start = start_time * update_frequency  # 计算绘图开始的时间步，通过将开始时间乘以更新频率。
        stop = stop_time * update_frequency  # 计算绘图结束的时间步，通过将结束时间乘以更新频率。
        orange = '#FF7F11'  #  定义一个橙色的颜色代码，用于绘图时的线条颜色。
        fig = plt.figure()  #  创建一个新的 Matplotlib 图形对象。
        ax = plt.axes(projection='3d')  # 在图形上创建一个三维坐标轴。
    #    ax.set_title(r'\textbf{3D Track}')  # 设置图形的标题，采用 LaTeX 语法显示粗体文本。
        ax.set_title(r'3D Track')  
        ax.set_xlabel(r'x [$m$]')  # 设置 x 轴标签，采用 LaTeX 语法显示米单位。
        ax.set_ylabel(r'y [$m$]')  # 设置 y 轴标签，采用 LaTeX 语法显示米单位。
        ax.set_zlabel(r'Altitude [$m$]')  # 设置 z 轴标签，采用 LaTeX 语法显示米单位。
        xline = self.lat_m[start:stop]  # 从存储的经度数据中提取在指定时间范围内的数据。
        yline = self.long_m[start:stop]  # 从存储的纬度数据中提取在指定时间范围内的数据。
        zline = [x / 3.28 for x in self.alt[start:stop]]  # 从存储的海拔高度数据中提取在指定时间范围内的数据，并将其转换为米。
        ax.plot3D(xline, yline, zline, linestyle='--', color=orange)  # 在三维坐标轴上绘制轨迹，采用虚线样式，橙色。

        # 添加红色直线
        x_start, y_start, z_start = 0, 0, 39.63414634146342
        x_end, y_end, z_end = -1809.2, -24.5, 39.63414634146342
        ax.plot3D([x_start, x_end], [y_start, y_end], [z_start, z_end], 'blue')

        ax.set_box_aspect((np.ptp(xline), np.ptp(yline), 11*np.ptp(zline)))   # 设置三维坐标轴的盒状外观，以确保比例一致性。
        # plt.savefig('plots/box.eps')  # 将图形保存为 EPS 文件。
        plt.savefig('plots/box')
        # plt.show()  # 显示绘制的三维轨迹图。