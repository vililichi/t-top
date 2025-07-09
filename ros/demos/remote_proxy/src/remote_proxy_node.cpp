#include <hbba_lite/core/DesireSet.h>
#include <hbba_lite/core/RosFilterPool.h>
#include <hbba_lite/core/GecodeSolver.h>
#include <hbba_lite/core/HbbaLite.h>
#include <hbba_lite/core/RosStrategyStateLogger.h>

#include <t_top_hbba_lite/Strategies.h>

#include <daemon_ros_client/msg/base_status.hpp>
#include <std_msgs/msg/u_int8.hpp>

#include <memory>
#include <algorithm>

using namespace std;

constexpr bool WAIT_FOR_SERVICE = true;
constexpr const char* NODE_NAME = "remote_proxy_node";

void publish_volume(uint8_t volume, rclcpp::Publisher<std_msgs::msg::UInt8>::SharedPtr volumePublisher)
{
    std_msgs::msg::UInt8 msg;
    msg.data = volume;
    volumePublisher->publish(msg);
}

int startNode()
{
    auto node = rclcpp::Node::make_shared(NODE_NAME);
    auto callbackGroup = node->create_callback_group(rclcpp::CallbackGroupType::Reentrant);
    daemon_ros_client::msg::BaseStatus::SharedPtr baseStatusMsg;
    auto volumePublisher = node->create_publisher<std_msgs::msg::UInt8>("daemon/set_volume", 1);

    // Create service for chat tools function call

    rclcpp::SubscriptionOptions options;
    options.callback_group = callbackGroup;
    auto baseStatusSubscriber = node->create_subscription<daemon_ros_client::msg::BaseStatus>(
        "daemon/base_status",
        1,
        [node, &baseStatusMsg](const daemon_ros_client::msg::BaseStatus::SharedPtr msg) { baseStatusMsg = msg; },
        options);

    auto desireSet = make_shared<DesireSet>();
    auto rosFilterPool = make_unique<RosFilterPool>(node, WAIT_FOR_SERVICE);
    auto filterPool = make_shared<RosLogFilterPoolDecorator>(node, move(rosFilterPool));

    vector<unique_ptr<BaseStrategy>> strategies;

    strategies.emplace_back(createManualChatStrategy(filterPool, desireSet, node));
    //strategies.emplace_back(createNearestFaceFollowingStrategy(filterPool));
    //strategies.emplace_back(createTooCloseReactionStrategy(filterPool));

    auto solver = make_unique<GecodeSolver>();
    auto strategyStateLogger = make_unique<RosTopicStrategyStateLogger>(node);
    HbbaLite hbba(desireSet, move(strategies), {{"sound", 1}}, move(solver), move(strategyStateLogger));

    desireSet->addDesire(make_unique<ManualChatDesire>());
    //desireSet->addDesire(make_unique<NearestFaceFollowingDesire>());
    //desireSet->addDesire(make_unique<TooCloseReactionDesire>());

    rclcpp::executors::MultiThreadedExecutor executor(rclcpp::ExecutorOptions(), 2);

    RCLCPP_INFO_STREAM(node->get_logger(), "Remote proxy started");
    executor.add_node(node);
    executor.spin();
    return 0;
}

int main(int argc, char** argv)
{
    rclcpp::init(argc, argv);

    try
    {
        return startNode();
    }
    catch (const std::exception& e)
    {
        RCLCPP_ERROR_STREAM(rclcpp::get_logger(NODE_NAME), "Remote proxy crashed (" << e.what() << ")");
        return -1;
    }

    rclcpp::shutdown();
}