# 代码注释规范

## 核心原则

**注释语言：所有注释必须使用中文**

**注释详细程度：详细注释**

## 注释要求

- 每个类必须有类级别的文档注释
- 每个公共方法必须有详细的文档注释
- 复杂的逻辑块必须有行内注释说明
- 关键算法和业务逻辑必须有注释解释"为什么"这样做
- 所有注释必须使用中文

## Python 示例

```python
class UserService:
    """
    用户服务类

    负责处理所有与用户相关的业务逻辑，包括用户注册、登录、
    信息更新等操作。

    Attributes:
        db: 数据库连接对象
        logger: 日志记录器
    """

    def __init__(self, db, logger):
        """
        初始化用户服务

        Args:
            db: 数据库连接对象，用于执行数据库操作
            logger: 日志记录器，用于记录操作日志
        """
        self.db = db
        self.logger = logger

    def register_user(self, username, email, password):
        """
        注册新用户

        执行用户注册流程，包括验证输入、检查用户是否已存在、
        加密密码、保存到数据库等步骤。

        Args:
            username (str): 用户名，长度必须在 3-20 个字符之间
            email (str): 电子邮件地址，必须是有效的邮箱格式
            password (str): 密码，长度必须至少 8 个字符

        Returns:
            dict: 包含用户信息的字典，格式为：
                {
                    'id': 用户ID,
                    'username': 用户名,
                    'email': 邮箱,
                    'created_at': 创建时间
                }

        Raises:
            ValueError: 当输入参数不符合要求时
            UserExistsError: 当用户名或邮箱已被注册时
            DatabaseError: 当数据库操作失败时
        """
        # 验证输入参数的有效性
        self._validate_registration_input(username, email, password)

        # 检查用户名是否已存在
        # 这一步很重要，避免重复注册
        if self._user_exists(username, email):
            self.logger.warning(f"注册失败：用户名 {username} 或邮箱 {email} 已存在")
            raise UserExistsError("用户名或邮箱已被注册")

        # 加密密码
        # 使用 bcrypt 算法进行加密，确保密码安全
        hashed_password = self._hash_password(password)

        # 保存用户到数据库
        try:
            user = self.db.create_user(
                username=username,
                email=email,
                password=hashed_password
            )
            self.logger.info(f"用户注册成功：{username}")
            return user
        except Exception as e:
            # 数据库操作失败，记录错误并抛出
            self.logger.error(f"用户注册失败：{str(e)}")
            raise DatabaseError(f"注册用户时发生数据库错误：{str(e)}")
```

## JavaScript/TypeScript 示例

```javascript
/**
 * 用户服务类
 *
 * 负责处理所有与用户相关的业务逻辑，包括用户注册、登录、
 * 信息更新等操作。
 */
class UserService {
    /**
     * 初始化用户服务
     *
     * @param {Object} db - 数据库连接对象，用于执行数据库操作
     * @param {Object} logger - 日志记录器，用于记录操作日志
     */
    constructor(db, logger) {
        this.db = db;
        this.logger = logger;
    }

    /**
     * 注册新用户
     *
     * 执行用户注册流程，包括验证输入、检查用户是否已存在、
     * 加密密码、保存到数据库等步骤。
     *
     * @param {string} username - 用户名，长度必须在 3-20 个字符之间
     * @param {string} email - 电子邮件地址，必须是有效的邮箱格式
     * @param {string} password - 密码，长度必须至少 8 个字符
     * @returns {Promise<Object>} 包含用户信息的对象
     * @throws {ValueError} 当输入参数不符合要求时
     * @throws {UserExistsError} 当用户名或邮箱已被注册时
     * @throws {DatabaseError} 当数据库操作失败时
     */
    async registerUser(username, email, password) {
        // 验证输入参数的有效性
        this._validateRegistrationInput(username, email, password);

        // 检查用户名是否已存在
        // 这一步很重要，避免重复注册
        if (await this._userExists(username, email)) {
            this.logger.warning(`注册失败：用户名 ${username} 或邮箱 ${email} 已存在`);
            throw new UserExistsError('用户名或邮箱已被注册');
        }

        // 加密密码
        // 使用 bcrypt 算法进行加密，确保密码安全
        const hashedPassword = await this._hashPassword(password);

        // 保存用户到数据库
        try {
            const user = await this.db.createUser({
                username,
                email,
                password: hashedPassword
            });
            this.logger.info(`用户注册成功：${username}`);
            return user;
        } catch (error) {
            // 数据库操作失败，记录错误并抛出
            this.logger.error(`用户注册失败：${error.message}`);
            throw new DatabaseError(`注册用户时发生数据库错误：${error.message}`);
        }
    }
}
```

## Java 示例

```java
/**
 * 用户服务类
 *
 * 负责处理所有与用户相关的业务逻辑，包括用户注册、登录、
 * 信息更新等操作。
 */
public class UserService {
    private final Database db;
    private final Logger logger;

    /**
     * 初始化用户服务
     *
     * @param db 数据库连接对象，用于执行数据库操作
     * @param logger 日志记录器，用于记录操作日志
     */
    public UserService(Database db, Logger logger) {
        this.db = db;
        this.logger = logger;
    }

    /**
     * 注册新用户
     *
     * 执行用户注册流程，包括验证输入、检查用户是否已存在、
     * 加密密码、保存到数据库等步骤。
     *
     * @param username 用户名，长度必须在 3-20 个字符之间
     * @param email 电子邮件地址，必须是有效的邮箱格式
     * @param password 密码，长度必须至少 8 个字符
     * @return 包含用户信息的对象
     * @throws ValueError 当输入参数不符合要求时
     * @throws UserExistsError 当用户名或邮箱已被注册时
     * @throws DatabaseError 当数据库操作失败时
     */
    public User registerUser(String username, String email, String password)
            throws ValueError, UserExistsError, DatabaseError {
        // 验证输入参数的有效性
        validateRegistrationInput(username, email, password);

        // 检查用户名是否已存在
        // 这一步很重要，避免重复注册
        if (userExists(username, email)) {
            logger.warning(String.format("注册失败：用户名 %s 或邮箱 %s 已存在", username, email));
            throw new UserExistsError("用户名或邮箱已被注册");
        }

        // 加密密码
        // 使用 bcrypt 算法进行加密，确保密码安全
        String hashedPassword = hashPassword(password);

        // 保存用户到数据库
        try {
            User user = db.createUser(username, email, hashedPassword);
            logger.info(String.format("用户注册成功：%s", username));
            return user;
        } catch (Exception e) {
            // 数据库操作失败，记录错误并抛出
            logger.error(String.format("用户注册失败：%s", e.getMessage()));
            throw new DatabaseError(String.format("注册用户时发生数据库错误：%s", e.getMessage()));
        }
    }
}
```
