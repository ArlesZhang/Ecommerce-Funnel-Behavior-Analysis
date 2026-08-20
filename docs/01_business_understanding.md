# Olist 电商平台业务理解报告

## 1. 平台概况

- **时间范围**：2016-09 ~ 2018-10（约 25 个月），有效运营期从 2017-01 开始
- **订单规模**：99,441 笔订单，97.02% 送达
- **用户规模**：96,096 位唯一用户（customer_unique_id），月活约 6,500 单
- **供给侧**：3,095 位卖家，32,951 个商品，73 个品类

## 2. 数据关系

```
customers ----(customer_id)----> orders ----(order_id)----> order_items ----(product_id)----> products
                                   |                           +----(seller_id)----> sellers
                                   +----(order_id)----> order_payments
                                   +----(order_id)----> order_reviews
geolocation ----(zip_code_prefix)----> customers / sellers
```

## 3. 关键发现

### 3.1 品类表现
- **订单量 Top 3**：bed_bath_table (9,417)、health_beauty (8,836)、sports_leisure (7,720)
- **GMV Top 3**：health_beauty (R$1.26M)、watches_gifts (R$1.21M)、bed_bath_table (R$1.04M)
- watches_gifts 订单量仅排第 7，但 GMV 第 2 → 高客单价品类，值得关注

### 3.2 用户行为
- 复购率仅 3.00%（2,801 / 93,358），绝大多数用户只买一次
- 复购用户平均购买 2.15 次，最高 15 次
- 用户高度集中在圣保罗州（SP 占 41.94%）

### 3.3 交易特征
- 平均客单价 R$137.75，中位数 R$86.90（右偏分布，少数大单拉高均值）
- 73.92% 用信用卡支付，boleto 占 19.04%
- 平均每单 1.14 件商品 → 绝大多数是单件购买

### 3.4 运营效率
- 下单到送达平均 12.6 天（审批 10.3h → 揽收 2.8 天 → 运输 9.3 天）
- 评价 J 型分布：57.78% 五星，11.51% 一星

## 4. !! 关键数据陷阱

1. **customer_id != 用户**：customer_id 是订单级身份，customer_unique_id 才是真实用户
   - 用 customer_id 做复购分析 → 复购率 0%（错误）
   - 用 customer_unique_id 做复购分析 → 复购率 3.00%（正确）
2. **订单状态过滤**：漏斗和 GMV 分析时需剔除 canceled/unavailable
3. **geolocation 去重**：同一 zip_code_prefix 有多条记录，join 前需去重
4. **品类名翻译**：品类名是葡萄牙语，展示前需 join 翻译表
