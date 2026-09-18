# 打开文件
with open('v2.log', 'r') as file:
    # 读取文件内容
    content = file.read()

# 统计 '*' 的次数
count = content.count('*')

# 输出结果
print(f"文件中 '*' 出现的次数为: {count}")
