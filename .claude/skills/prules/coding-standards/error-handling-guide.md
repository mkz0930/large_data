# 错误处理规范

## 核心原则

**详细的异常处理 + 日志记录 + 用户友好提示**

## 错误处理要求

- 每个可能出错的操作都要有 try-catch 包裹
- 所有错误都要记录到日志系统，包含足够的上下文信息
- 日志级别要合理使用：
  - `DEBUG`: 调试信息
  - `INFO`: 正常操作信息
  - `WARNING`: 警告信息（如参数验证失败）
  - `ERROR`: 错误信息（如外部服务调用失败）
  - `CRITICAL`: 严重错误（如未预期的异常）
- 向用户展示的错误信息必须友好、清晰、可操作
- 不要向用户暴露技术细节或敏感信息
- 为不同类型的错误创建自定义异常类

## Python 示例

```python
import logging

class PaymentService:
    def process_payment(self, user_id, amount):
        """
        处理支付请求

        Args:
            user_id (int): 用户ID
            amount (float): 支付金额

        Returns:
            dict: 支付结果

        Raises:
            ValueError: 参数无效
            InsufficientFundsError: 余额不足
            PaymentGatewayError: 支付网关错误
        """
        try:
            # 验证输入参数
            if amount <= 0:
                error_msg = "支付金额必须大于0"
                logging.warning(f"支付参数验证失败：用户 {user_id}，金额 {amount}")
                raise ValueError(error_msg)

            # 检查用户余额
            try:
                balance = self._get_user_balance(user_id)
            except DatabaseError as e:
                # 数据库查询失败
                logging.error(f"查询用户余额失败：用户 {user_id}，错误：{str(e)}")
                raise PaymentError("抱歉，系统暂时无法处理您的支付请求，请稍后重试")

            if balance < amount:
                # 余额不足
                logging.info(f"支付失败：用户 {user_id} 余额不足，当前余额 {balance}，需要 {amount}")
                raise InsufficientFundsError(
                    f"您的账户余额不足。当前余额：¥{balance:.2f}，需要支付：¥{amount:.2f}"
                )

            # 调用支付网关
            try:
                result = self._call_payment_gateway(user_id, amount)
                logging.info(f"支付成功：用户 {user_id}，金额 {amount}，交易ID {result['transaction_id']}")
                return {
                    'success': True,
                    'message': '支付成功！',
                    'transaction_id': result['transaction_id']
                }
            except PaymentGatewayError as e:
                # 支付网关错误
                logging.error(f"支付网关错误：用户 {user_id}，金额 {amount}，错误：{str(e)}")
                raise PaymentError(
                    "抱歉，支付处理失败，您的账户未被扣款。请稍后重试或联系客服。"
                )

        except ValueError as e:
            # 参数验证错误，直接向用户展示错误信息
            raise
        except InsufficientFundsError as e:
            # 余额不足，直接向用户展示错误信息
            raise
        except PaymentError as e:
            # 支付错误，直接向用户展示错误信息
            raise
        except Exception as e:
            # 未预期的错误，记录详细日志，向用户展示友好信息
            logging.critical(f"支付处理发生未预期错误：用户 {user_id}，金额 {amount}，错误：{str(e)}", exc_info=True)
            raise PaymentError(
                "抱歉，系统发生错误，请稍后重试。如果问题持续存在，请联系客服。"
            )
```

## JavaScript/TypeScript 示例

```javascript
class PaymentService {
    async processPayment(userId, amount) {
        try {
            // 验证输入参数
            if (amount <= 0) {
                const errorMsg = '支付金额必须大于0';
                logger.warning(`支付参数验证失败：用户 ${userId}，金额 ${amount}`);
                throw new ValueError(errorMsg);
            }

            // 检查用户余额
            let balance;
            try {
                balance = await this._getUserBalance(userId);
            } catch (error) {
                // 数据库查询失败
                logger.error(`查询用户余额失败：用户 ${userId}，错误：${error.message}`);
                throw new PaymentError('抱歉，系统暂时无法处理您的支付请求，请稍后重试');
            }

            if (balance < amount) {
                // 余额不足
                logger.info(`支付失败：用户 ${userId} 余额不足，当前余额 ${balance}，需要 ${amount}`);
                throw new InsufficientFundsError(
                    `您的账户余额不足。当前余额：¥${balance.toFixed(2)}，需要支付：¥${amount.toFixed(2)}`
                );
            }

            // 调用支付网关
            try {
                const result = await this._callPaymentGateway(userId, amount);
                logger.info(`支付成功：用户 ${userId}，金额 ${amount}，交易ID ${result.transactionId}`);
                return {
                    success: true,
                    message: '支付成功！',
                    transactionId: result.transactionId
                };
            } catch (error) {
                // 支付网关错误
                logger.error(`支付网关错误：用户 ${userId}，金额 ${amount}，错误：${error.message}`);
                throw new PaymentError(
                    '抱歉，支付处理失败，您的账户未被扣款。请稍后重试或联系客服。'
                );
            }

        } catch (error) {
            // 根据错误类型处理
            if (error instanceof ValueError ||
                error instanceof InsufficientFundsError ||
                error instanceof PaymentError) {
                // 已知错误，直接抛出
                throw error;
            } else {
                // 未预期的错误，记录详细日志，向用户展示友好信息
                logger.critical(
                    `支付处理发生未预期错误：用户 ${userId}，金额 ${amount}，错误：${error.message}`,
                    { stack: error.stack }
                );
                throw new PaymentError(
                    '抱歉，系统发生错误，请稍后重试。如果问题持续存在，请联系客服。'
                );
            }
        }
    }
}
```

## Java 示例

```java
public class PaymentService {
    private static final Logger logger = LoggerFactory.getLogger(PaymentService.class);

    /**
     * 处理支付请求
     *
     * @param userId 用户ID
     * @param amount 支付金额
     * @return 支付结果
     * @throws ValueError 参数无效
     * @throws InsufficientFundsError 余额不足
     * @throws PaymentError 支付错误
     */
    public PaymentResult processPayment(long userId, double amount)
            throws ValueError, InsufficientFundsError, PaymentError {
        try {
            // 验证输入参数
            if (amount <= 0) {
                String errorMsg = "支付金额必须大于0";
                logger.warn("支付参数验证失败：用户 {}，金额 {}", userId, amount);
                throw new ValueError(errorMsg);
            }

            // 检查用户余额
            double balance;
            try {
                balance = getUserBalance(userId);
            } catch (DatabaseError e) {
                // 数据库查询失败
                logger.error("查询用户余额失败：用户 {}，错误：{}", userId, e.getMessage());
                throw new PaymentError("抱歉，系统暂时无法处理您的支付请求，请稍后重试");
            }

            if (balance < amount) {
                // 余额不足
                logger.info("支付失败：用户 {} 余额不足，当前余额 {}，需要 {}", userId, balance, amount);
                throw new InsufficientFundsError(
                    String.format("您的账户余额不足。当前余额：¥%.2f，需要支付：¥%.2f", balance, amount)
                );
            }

            // 调用支付网关
            try {
                PaymentGatewayResult result = callPaymentGateway(userId, amount);
                logger.info("支付成功：用户 {}，金额 {}，交易ID {}", userId, amount, result.getTransactionId());
                return new PaymentResult(true, "支付成功！", result.getTransactionId());
            } catch (PaymentGatewayError e) {
                // 支付网关错误
                logger.error("支付网关错误：用户 {}，金额 {}，错误：{}", userId, amount, e.getMessage());
                throw new PaymentError(
                    "抱歉，支付处理失败，您的账户未被扣款。请稍后重试或联系客服。"
                );
            }

        } catch (ValueError | InsufficientFundsError | PaymentError e) {
            // 已知错误，直接抛出
            throw e;
        } catch (Exception e) {
            // 未预期的错误，记录详细日志，向用户展示友好信息
            logger.error("支付处理发生未预期错误：用户 {}，金额 {}，错误：{}", userId, amount, e.getMessage(), e);
            throw new PaymentError(
                "抱歉，系统发生错误，请稍后重试。如果问题持续存在，请联系客服。"
            );
        }
    }
}
```

## 自定义异常类示例

### Python

```python
class PaymentError(Exception):
    """支付相关的基础异常类"""
    pass

class InsufficientFundsError(PaymentError):
    """余额不足异常"""
    pass

class PaymentGatewayError(PaymentError):
    """支付网关异常"""
    pass

class DatabaseError(Exception):
    """数据库操作异常"""
    pass
```

### JavaScript/TypeScript

```javascript
class PaymentError extends Error {
    constructor(message) {
        super(message);
        this.name = 'PaymentError';
    }
}

class InsufficientFundsError extends PaymentError {
    constructor(message) {
        super(message);
        this.name = 'InsufficientFundsError';
    }
}

class PaymentGatewayError extends PaymentError {
    constructor(message) {
        super(message);
        this.name = 'PaymentGatewayError';
    }
}
```

### Java

```java
public class PaymentError extends Exception {
    public PaymentError(String message) {
        super(message);
    }
}

public class InsufficientFundsError extends PaymentError {
    public InsufficientFundsError(String message) {
        super(message);
    }
}

public class PaymentGatewayError extends PaymentError {
    public PaymentGatewayError(String message) {
        super(message);
    }
}
```
