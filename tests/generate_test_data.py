"""生成 20 份测试 Excel 文件，覆盖正常数据、空行、特殊字符、长文本等场景。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

OUTPUT_DIR = Path(__file__).parent / "test_data"
OUTPUT_DIR.mkdir(exist_ok=True)

QA_POOL = [
    ('如何重置密码？', '您可以在登录页面点击「忘记密码」链接进行重置。'),
    ('退款需要多长时间？', '退款通常在3-5个工作日内到账。'),
    ('如何联系客服？', '您可以通过在线聊天、电话400-123-4567或邮件support@example.com联系我们。'),
    ('会员有什么特权？', '会员享受专属折扣、优先客服、免费配送等权益。'),
    ('如何修改收货地址？', '在「我的订单」页面，找到对应订单，点击「修改地址」即可。'),
    ('支持哪些支付方式？', '支持支付宝、微信支付、银行卡、花呗等。'),
    ('订单可以取消吗？', '发货前均可取消，发货后需走退货流程。'),
    ('如何查看物流信息？', '在订单详情页可直接查看物流跟踪信息。'),
    ('发票怎么开？', '下单时勾选「开具发票」，或联系客服补开。'),
    ('商品质量有问题怎么办？', '7天内可无理由退换货，请保留商品原包装。'),
    ('优惠券怎么使用？', '在结算页面的优惠券栏输入券码或选择可用优惠券。'),
    ('积分怎么兑换？', '进入「积分商城」，选择商品兑换即可。'),
    ('注册需要什么信息？', '需要手机号、验证码和设置密码。'),
    ('可以用邮箱登录吗？', '目前仅支持手机号登录。'),
    ('如何开通自动续费？', '在「会员中心」设置页面开启自动续费。'),
]

SPECIAL_CHARS_QA = [
    ('价格是多少？（含税）', '含税价格请参考商品详情页，标注「¥」的为含税价。'),
    ('配送范围：北京/上海/广州', '目前支持全国配送，偏远地区可能加收运费。'),
    ('100%纯棉和涤纶混纺有什么区别？', '纯棉透气性好但易皱，混纺更耐穿易打理。'),
]

LONG_TEXT_QA = [
    (
        '我购买了一个电子产品，使用了大约两个月后出现了屏幕闪烁的问题，请问这种情况是否在保修范围内？如果在的话，我应该怎么操作才能申请保修服务？需要提供哪些材料？',
        '根据我们的保修政策，电子产品自购买之日起享有一年质保。屏幕闪烁属于硬件故障，在保修范围内。'
        '您需要提供购买凭证（订单截图或发票）、产品序列号，然后在官网「售后服务」页面提交保修申请。'
        '我们会在1-2个工作日内安排取件，维修周期约7-10个工作日。',
    ),
]


def generate_one(index: int, qa_rows: list[tuple[str, str]], filename: str):
    df = pd.DataFrame(qa_rows, columns=["Q", "A"])
    path = OUTPUT_DIR / filename
    df.to_excel(path, index=False, engine="openpyxl")
    print(f"  [{index:02d}] {filename}  ({len(qa_rows)} 行)")


def main():
    print(f"生成测试数据到 {OUTPUT_DIR}\n")

    # 1-10: 正常数据，不同行数
    for i in range(10):
        count = 5 + i
        rows = QA_POOL[:count]
        generate_one(i + 1, rows, f"normal_{i + 1:02d}.xlsx")

    # 11-13: 含特殊字符
    for i in range(3):
        rows = QA_POOL[:5] + SPECIAL_CHARS_QA[: i + 1]
        generate_one(11 + i, rows, f"special_chars_{i + 1:02d}.xlsx")

    # 14-15: 含长文本
    for i in range(2):
        rows = QA_POOL[:5] + LONG_TEXT_QA
        generate_one(14 + i, rows, f"long_text_{i + 1:02d}.xlsx")

    # 16-17: 含空行（Q 或 A 为空）
    for i in range(2):
        rows = list(QA_POOL[:5])
        rows.insert(2, ("", "答案但没有问题"))
        rows.insert(4, ("有问题但没答案", ""))
        generate_one(16 + i, rows, f"with_empty_{i + 1:02d}.xlsx")

    # 18: 只有必要列 Q/A
    generate_one(18, QA_POOL[:8], "minimal_columns.xlsx")

    # 19: 多余列
    extra_rows = [(q, a) for q, a in QA_POOL[:8]]
    df = pd.DataFrame(extra_rows, columns=["Q", "A"])
    df["类别"] = "通用"
    df["优先级"] = "高"
    path = OUTPUT_DIR / "extra_columns.xlsx"
    df.to_excel(path, index=False, engine="openpyxl")
    print(f"  [19] extra_columns.xlsx  ({len(df)} 行)")

    # 20: 列名大小写不同
    rows20 = QA_POOL[:6]
    df20 = pd.DataFrame(rows20, columns=["q", "a"])
    path20 = OUTPUT_DIR / "lowercase_cols.xlsx"
    df20.to_excel(path20, index=False, engine="openpyxl")
    print(f"  [20] lowercase_cols.xlsx  ({len(df20)} 行)")

    # 额外：生成 sample_data
    sample_dir = Path(__file__).parent.parent / "sample_data"
    sample_dir.mkdir(exist_ok=True)
    sample_df = pd.DataFrame(QA_POOL[:5], columns=["Q", "A"])
    sample_path = sample_dir / "sample_qa.xlsx"
    sample_df.to_excel(sample_path, index=False, engine="openpyxl")
    print(f"\n示例文件: {sample_path}")

    print(f"\n共生成 20 份测试文件 + 1 份示例文件")


if __name__ == "__main__":
    main()
