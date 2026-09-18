def compare_files(file1, file2):
    with open(file1, 'r') as f1, open(file2, 'r') as f2:
        lines1 = f1.readlines()
        lines2 = f2.readlines()

    if len(lines1) != len(lines2):
        print("文件长度不一致")
        return

    different_lines = []
    for i, (line1, line2) in enumerate(zip(lines1, lines2), 1):
        if line1 != line2:
            different_lines.append((i, line1.strip(), line2.strip()))

    if not different_lines:
        print("文件完全一致")
    else:
        print("文件不一致的行:")
        for line in different_lines:
            print("行号:", line[0])
            print("文件1内容:", line[1])
            print("文件2内容:", line[2])
            print()

# 请将文件路径替换为你的文件路径
file1_path = "resultv6.mtx"
file2_path = "resultv10.mtx"

compare_files(file1_path, file2_path)