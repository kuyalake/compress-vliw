#include "mymethod.h"

// 比较函数，用于在排序时保留原始位置
bool comparePairs(const Pair& a, const Pair& b) {
    return a.value < b.value;
}


void readMatrixMarket(const char* filename, vector<float>& CAx, vector<int>& CAi, vector<int>& CAp, int* p_n, long int* p_nnz) {
    ifstream file(filename);

    if (!file.is_open()) {
        cerr << "Error: Unable to open file " << filename << endl;
        exit(1);
    }

    string line;
    int rows, cols, nnz;
    bool isSymmetric = false;

    while (getline(file, line)) {
        if (line[0] != '%') {
            istringstream iss(line);
            iss >> rows >> cols >> nnz;
            break;
        }
    }
    *p_n = cols;
    *p_nnz = nnz;
    CAx.resize(nnz);
    CAi.resize(nnz);
    CAp.resize(cols + 1, 0);

    int row, col;
    float val;

    for (int i = 0; i < nnz; i++) {
        file >> row >> col >> val;
        CAx[i] = val;
        CAi[i] = row - 1; // Convert to 0-based indexing
        CAp[col]++;
        if (row != col) // Non-diagonal element
            isSymmetric = true;
    }

    if (!isSymmetric) {
        for (int i = 1; i <= cols; i++)
            CAp[i] += CAp[i - 1];
    } else {
        // If symmetric, do additional processing
        for (int i = 1; i <= cols; i++) {
            CAp[i] += CAp[i - 1];
        }
    }
}

void cscToCsr(
    const std::vector<float>& CAx, // CSC存储的矩阵非零元素
    const std::vector<int>& CAi, // CSC存储的行索引
    const std::vector<int>& CAp, // CSC存储的列指针
    std::vector<float>& RAx,       // 转换后的CSR存储的矩阵非零元素
    std::vector<int>& RAi,       // 转换后的CSR存储的列索引
    std::vector<int>& RAp        // 转换后的CSR存储的行指针
) {
    int numCols = CAp.size() - 1; // 矩阵的列数
    int numNonZero = CAx.size();  // 非零元素的数量

    // 初始化行指针
    RAp.resize(numCols + 1, 0);

    // 统计每一列的非零元素数量
    for (int i = 0; i < numNonZero; i++) {
        RAp[CAi[i] + 1]++;
    }

    // 累加得到行指针
    for (int i = 1; i <= numCols; i++) {
        RAp[i] += RAp[i - 1];
    }

    // 复制非零元素和列索引
    RAx.resize(numNonZero);
    RAi.resize(numNonZero);

    std::vector<int> rowCounter(numCols, 0);

    for (int j = 0; j < numCols; j++) {
        for (int k = CAp[j]; k < CAp[j + 1]; k++) {
            int i = CAi[k];
            int dest = RAp[i] + rowCounter[i];
            RAx[dest] = CAx[k];
            RAi[dest] = j;
            rowCounter[i]++;
        }
    }
}

void printSparse(
    const std::vector<float>& Ax, // 非零元素
    const std::vector<int>& Ai, // 索引
    const std::vector<int>& Ap // 指针
){
    cout << "Ax: ";
    for (float val : Ax) {
        cout << val << " ";
    }
    cout << endl;

    cout << "Ai: ";
    for (int val : Ai) {
        cout << val << " ";
    }
    cout << endl;

    cout << "Ap: ";
    for (int val : Ap) {
        cout << val << " ";
    }
    cout << endl;
}


std::vector<int> extractSubVectorInt(const std::vector<int>& original, int start, int end) {
    std::vector<int> subVector;
    if (start < 0 || end >= original.size() || start > end) {
        std::cout << "Invalid range\n";
        return subVector;
    }

    for (int i = start; i <= end; ++i) {
        subVector.push_back(original[i]);
    }

    return subVector;
}

std::vector<float> extractSubVectorFloat(const std::vector<float>& original, int start, int end) {
    std::vector<float> subVector;
    if (start < 0 || end >= original.size() || start > end) {
        std::cout << "Invalid range\n";
        return subVector;
    }

    for (int i = start; i <= end; ++i) {
        subVector.push_back(original[i]);
    }

    return subVector;
}

void addMissingElements(const std::vector<int>& Ai, int start, int end, std::vector<int>& subAi, std::vector<float>& subAx, std::vector<int>& myQue) {
    for (int i = start; i <= end; ++i) {
        if (std::find(subAi.begin(), subAi.end(), Ai[i]) == subAi.end()) {
            subAi.push_back(Ai[i]);
            subAx.push_back(0);
            myQue.push_back(Ai[i]);
        }
    }
}

void addMissingElementsFalse(const std::vector<int>& Ai, int start, int end, std::vector<int>& subAi, std::vector<float>& subAx, std::vector<int>& myQue) {
    for (int i = start; i <= end; ++i) {
        if (std::find(subAi.begin(), subAi.end(), Ai[i]) == subAi.end()) {
            subAi.push_back(Ai[i]);
            subAx.push_back(99999);
            myQue.push_back(Ai[i]);
        }
    }
}

int findRowPosition(const std::vector<int>& Ai_new, int row) {
    for (size_t i = 0; i < Ai_new.size(); ++i) {
        if (Ai_new[i] == row) {
            return i;
        }
    }
    return -1; // 如果未找到，返回-1表示未找到
}


int fillIn(
    const std::vector<float>& Ax, // 非零元素
    const std::vector<int>& Ai, // 索引
    const std::vector<int>& Ap, // 指针
    const int n, //order
    const int nnz, //number of non-zeros
    std::vector<float>& Ax_fill, //非零元素after fill in
    std::vector<int>& Ai_fill, // 索引after fill in
    std::vector<int>& Ap_fill,  //指针after fill in
    std::vector<int>& Ad_fill  //对角元素指针after fill in
){
    int j, k;
    int row;
    int col_nnz;
    
    Ap_fill.push_back(0);
    Ap_fill.push_back(Ap[1] - Ap[0]);
    Ad_fill.push_back(0);

    std::vector<int> Ai_0 = extractSubVectorInt(Ai, Ap[0], Ap[1] - 1);
    Ai_fill.insert(Ai_fill.end(), Ai_0.begin(), Ai_0.end());

    std::vector<float> Ax_0 = extractSubVectorFloat(Ax, Ap[0], Ap[1] - 1);
    Ax_fill.insert(Ax_fill.end(), Ax_0.begin(), Ax_0.end());

    for (int k = 1; k < n; k++)
    {
        std::vector<int> subAi = extractSubVectorInt(Ai, Ap[k], Ap[k + 1] - 1);
        std::vector<float> subAx = extractSubVectorFloat(Ax, Ap[k], Ap[k + 1] - 1);
        std::vector<int> myQue = extractSubVectorInt(Ai, Ap[k], Ap[k + 1] - 1);

        std::cout << "handling column " << k;

        std::cout << "\nSubAi: ";
        for (int i : subAi) 
        {
            std::cout << i << " ";
        }

        std::cout << "\nSubAx: ";
        for (float i : subAx) 
        {
            std::cout << i << " ";
        }

        while (!myQue.empty())
        {
            row = myQue.front();
//            cout << "Analyzing A(" << row << "," << k << ")";

            if (row < k) //需要检查左列，注意左列是已经完成fill in填充的
           {
                cout << "\tChecked!\n";
                addMissingElements(Ai_fill, Ad_fill[row] + 1, Ap_fill[row + 1] - 1, subAi, subAx, myQue);
                //addMissingElementsFalse(Ai_fill, Ad_fill[row] + 1, Ap_fill[row + 1] - 1, subAi, subAx, myQue);  
            }
            myQue.erase(myQue.begin());
        }

        // 创建一个包含原始位置和值的 Pair 结构体的向量
        std::vector<Pair> pairs;
        for (int i = 0; i < subAi.size(); ++i) {
            pairs.push_back({i, subAi[i]});
        }

        // 对 Ai 进行排序，同时保留原始位置信息
        std::sort(pairs.begin(), pairs.end(), comparePairs);

        // 创建新的 Ai 和 Ax 向量
        std::vector<int> Ai_new;
        std::vector<float> Ax_new;

        // 根据排序后的顺序重排 Ai 和 Ax
        for (const Pair& p : pairs) 
        {
            Ai_new.push_back(p.value);
            Ax_new.push_back(subAx[p.index]);
        }

        // 输出结果
        std::cout << "Sorted Ai: ";
        for (int val : Ai_new) 
        {
            std::cout << val << " ";
        }
        std::cout << "\n";

        std::cout << "Corresponding Ax: ";
        for (float val : Ax_new) 
        {
            std::cout << val << " ";
        }
        std::cout << "\n";

        Ai_fill.insert(Ai_fill.end(), Ai_new.begin(), Ai_new.end());
        Ax_fill.insert(Ax_fill.end(), Ax_new.begin(), Ax_new.end());
        Ap_fill.push_back(Ap_fill[k] + Ai_new.size());
        int position = findRowPosition(Ai_new, k);
        if (position != -1) 
        {
            Ad_fill.push_back(Ap_fill[k] + position);
        } else 
        {
            std::cout << "Element " << k << " not found in Ai_new" << std::endl;
            return -1;
        }
/*
        std::cout << "Now Ai_fill is : ";
        for (int val : Ai_fill) 
        {
            std::cout << val << " ";
        }
        std::cout << "\n";

        std::cout << "Now Ax_fill is : ";
        for (float val : Ax_fill) 
        {
            std::cout << val << " ";
        }
        std::cout << "\n";

        std::cout << "Now Ap_fill is : ";
        for (int val : Ap_fill) 
        {
            std::cout << val << " ";
        }
        std::cout << "\n";

        std::cout << "Now Ad_fill is : ";
        for (int val : Ad_fill) 
        {
            std::cout << val << " ";
        }
        std::cout << "\n";
*/
    }
    return 0;
}

void writeCSCtoMTX(const std::vector<float>& Ax, const std::vector<int>& Ai, const std::vector<int>& Ap, const int numRows, const int numCols, const int numNonZero, const std::string& filename) {
    std::ofstream file(filename);

    if (!file.is_open()) {
        std::cerr << "Error: Unable to open file " << filename << std::endl;
        return;
    }

    file << "%%MatrixMarket matrix coordinate real general" << std::endl;
    file << numRows << " " << numCols << " " << numNonZero << std::endl;

    for (int j = 0; j < numCols; ++j) {
        for (int i = Ap[j]; i < Ap[j + 1]; ++i) {
            file << Ai[i] + 1 << " " << j + 1 << " " << Ax[i] << std::endl; // Ai, Aj 是从1开始的，所以需要+1
        }
    }

    file.close();
}

long int divCount(const std::vector<int>& Ap, const std::vector<int>& Ad, const int n) {
    long int sum = 0;
    int column_divcount;
//    cout << "\n\n";
    for (int k = 0; k < n; k++){
        column_divcount = Ap[k + 1] - 1 - Ad[k];
        sum += column_divcount;
//        cout << "column " << k << " divcount is: " << column_divcount << endl;
//        cout << "now div sum is: " << sum << endl;
    }
    return sum;
}

long int msCount(const std::vector<int>& Ai, const std::vector<int>& Ap, const std::vector<int>& Ad, const int n){
    long int sum = 0;
    int column_mscount;
//    cout << "\n\n";
    for (int k = 0; k < n; k++){
        column_mscount = 0;
        for (int j = Ap[k]; j < Ad[k]; j++){
            int row = Ai[j];
            column_mscount += Ap[row + 1] - 1 - Ad[row];
        }

        sum += column_mscount;
//        cout << "column " << k << " mscount is: " << column_mscount << endl;
//        cout << "now ms sum is: " << sum << endl;        
    }
    return sum;
}

int searchElement(const std::vector<int>& vec, int start, int end, int row, int* p_location) {
    // 确保 start 和 end 在有效范围内
    if (start >= vec.size() || end >= vec.size() || start > end) {
        std::cerr << "Invalid range." << std::endl;
        return 0;
    }

    // 在指定范围内寻找值为 row 的元素
    for (int i = start; i <= end; ++i) {
        if (vec[i] == row) {
            *p_location = i;
            return 1;  // 找到了
        }
    }

    return 0;  // 没有找到
}

int buildGraph(EleNode* EleNodePointer[], int n, const std::vector<int>& Ai, const std::vector<int>& Ap, const std::vector<int>& Ad) {
    int ele = 0;
    for (int k = 0; k < n; k++) {
        for (int p = Ap[k]; p < Ap[k + 1]; p ++, ele++) {
            int row = Ai[p];
            cout << "this is ele : " << ele << endl;
            cout << "col is " << k << ", row is " << row << endl;
            EleNodePointer[ele] = new EleNode(ele); //创建并初始化 EleNode 对象，将指针保存到数组中
            EleNodePointer[ele]->setAi(ele);

            if (p == Ap[k]) { //是该列的最上面一个元素，肯定不用更新
                EleNodePointer[ele]->setValid(1);
                EleNodePointer[ele]->setToDo(0);
            }
            else { //不是第一个元素，要依次检查上方元素是否有对该元素的更新
                int valid = 1;
                int to_do = 0;
                int location;
                for (int j = Ap[k]; (j < p) && (j < Ad[k]); j++) {
                    int col = Ai[j];
//                    cout << "searching in col " << j << endl;
                    int found = searchElement(Ai, Ap[col], Ap[col + 1] - 1, row, &location);
                    if (found) { //这个元素依赖于col列
                        valid = 0;
                        to_do ++; 
                        EleNodePointer[location]->addChild(ele); //给依赖对象 location 增加child
                        EleNodePointer[j]->addChild(ele); //同时别忘了给乘数 j 增加child
                        //因为依赖关系是element to element，所以不用担心重复
                        //OpPack newpair = {j, location, ele, 0}; // A = j, B = location, C = ele
                        OpPack newpair;
                        newpair.rs = j;
                        newpair.rt = location;
                        newpair.c = ele;
                        newpair.op = 0;
                        EleNodePointer[ele]->pool.push_back(newpair);
                    }
                }

                if (p > Ad[k]) { //下三角元素额外处理
                    cout << ele << " divided\n";
                    valid = 0;
                    to_do ++;
                    EleNodePointer[Ad[k]]->addChild(ele);  //给依赖对象对角元素增加child
                    //OpPack newpair = {Ad[k], -1, ele, 1}; //C = ele, A = Ad[k]
                    OpPack newpair;
                    newpair.rs = Ad[k];
                    //newpair.rt = -1;
                    newpair.c = ele;
                    newpair.op = 1;
                    EleNodePointer[ele]->pool.push_back(newpair);
                }
            //    else //单独处理最后一个pair 
            //    {
            //        if (!EleNodePointer[ele]->pool.empty()) {
            //            EleNodePointer[ele]->pool.back().last = 1;
            //        }
            //    }

                EleNodePointer[ele]->setValid(valid);
                EleNodePointer[ele]->setToDo(to_do);
            }

            cout << ele << " returned\n";
        }
    }
    return 0;
}

int initialWl(EleNode* EleNodePointer[], int nnz, std::vector<OpPack>& wl) {
    for (int ele = 0; ele < nnz; ele++) {
        if (EleNodePointer[ele]->getValid()) {
//            cout << "the valid element is " << ele << endl;
            std::vector<int> child = EleNodePointer[ele]->getChild();
            for (auto it = child.begin(); it != child.end(); ++it) {
                std::vector<OpPack>& pool = EleNodePointer[*it]->pool;
                for (auto p = pool.begin(); p != pool.end(); ++p) {
                    if (p->op == 1) {
                        //检查除法
                        if ((p->rs == ele) && (p == pool.begin())) {
                            wl.push_back(*p);
                            p = pool.erase(p);
                            --p;
                        }
                    }
                    else {
                        //检查ms
                        if (p->rs == ele) {
                            if (EleNodePointer[p->rt]->getValid())
                            {
                                wl.push_back(*p);
                                p = pool.erase(p);
                                --p;
                            }
                        }
                        else if (p->rt == ele) {
                            if (EleNodePointer[p->rs]->getValid())
                            {
                                wl.push_back(*p);
                                p = pool.erase(p);
                                --p;
                            }
                        }
                    }

                    if (pool.size() == 1)
                    {
                        //检查一下最后的除法可不可以做
                        if (((p + 1)->op == 1) && EleNodePointer[(p + 1)->rs]->getValid()) //最后一个操作就是除法，且rs已经ready
                        {
                            ++p;
                            wl.push_back(*p);
                            p = pool.erase(p);
                            --p;
                        }
                    }
                }
            }
//            std::cout << "waiting list is: " << endl;
//            for (const auto& element : wl) {
//                std::cout << "<" << element.rs << "," << element.rt << "," << element.c << "," << element.op << "> " << endl;;
//            }
        }
//        std::cout << ele << " returned!\n";
    }
    return 1;
}

int findC(const std::vector<OpPack>& pool, int c) {
    for (int i = 0; i < pool.size(); ++i) {
        if (pool[i].c == c) {
            return 1;
        }
    }
    return 0; // 如果未找到，返回0表示未找到
}

void addOkToDo(std::vector<OpPack>& wl, std::vector<OpPack>& pool, int time) {
    for (auto it = wl.begin(); it != wl.end(); ++it) {
        //要求1：新加入的pair的c不能与pool中原有的c重合
        int found = findC(pool, it->c);
        if (!found) //未找到，可以加入
        {
                pool.push_back(*it);
                it = wl.erase(it);
                --it;
        }
    }
}

int check(int value, std::vector<int>* vec) {
    for (auto it = vec->begin(); it != vec->end(); ++it) {
        if (value % NBANK == *it % NBANK) {
            if (value == *it)
                return 2; //已有该元素
            else
                return 0; //访存冲突
        }
    }
    return 1; //没有找到
}

void schedule(InstPack inst[][NPE], std::vector<int>* ocp[], EleNode* EleNodePointer[], std::vector<OpPack>& pool, int i, std::vector<int>& newly_valid) {
    for (int j = 0; j < NPE; j++) {
        if (inst[i][j].valid) //已经被填充了，跳过
            continue;
        //找到一个空位，开始在pool中逐个寻找合适的元素，直到pool结尾
        for (auto it = pool.begin(); it != pool.end(); ++it) {
            //首先判断it的操作类型
            if (it->op) //是除法
            {
//                //判定操作数是否ready
//                if ((EleNodePointer[it->c]->getTime() > i) || (EleNodePointer[it->rs]->getTime() > i))
//                    continue;
                //判定除数和被除数是否冲突 rs c
                if (it->rs % NBANK == it->c % NBANK) //冲突啦，需要两个连续的slot：i i+1
                {
                    //判定操作数是否ready
                    if ((EleNodePointer[it->c]->getTime() > (i + 1)) || (EleNodePointer[it->rs]->getTime() > i))
                        continue;
                    //检查rs能否放入i
                    int ok1 = check(it->rs, ocp[i]);
                    if (!ok1) continue;
                    //检查c能否放入i+1
                    int ok2 = check(it->c, ocp[i + 1]);
                    if (!ok2) continue;
                    //满足条件！将该操作调度到i和i+1的PE j上
                    inst[i][j].rt = it->rs;
                    inst[i][j].op = 3;
                    inst[i][j].sel1 = 1;
                    inst[i][j].valid = 1;
                    inst[i + 1][j].rs = it->c;
                    inst[i + 1][j].op = 3;
                    inst[i + 1][j].sel1 = 0; //仅rs接入，rt保持不变
                    inst[i + 1][j].valid = 1;
                    //处理该操作带来的后果
                    EleNodePointer[it->c]->setTime(i + 1 + DELAY);
                    int remain = EleNodePointer[it->c]->getToDo();
                    if (remain == 1)
                    {
                        EleNodePointer[it->c]->setValid(1);
                        newly_valid.push_back(it->c);
                    }
                    EleNodePointer[it->c]->setToDo(remain - 1);
                        
                    if (ok1 == 1) ocp[i]->push_back(it->rs);
                    ocp[i + 1]->push_back(it->c);
                    //在pool中删除该操作
                    it = pool.erase(it);
                    --it;
                    //进行下一个j
                    break;
                }
                else //没有冲突，只需要一个slot: i
                {
                    //判定操作数是否ready
                    if ((EleNodePointer[it->c]->getTime() > i) || (EleNodePointer[it->rs]->getTime() > i))
                        continue;
                    //检查rs能否放入i
                    int ok1 = check(it->rs, ocp[i]);
                    if (!ok1) continue;
                    //检查c能否放入i
                    int ok2 = check(it->c, ocp[i]);
                    if (!ok2) continue;
                    //满足条件！将该操作调度到i的PE j上
                    inst[i][j].rs = it->c;
                    inst[i][j].rt = it->rs;
                    inst[i][j].op = 3;
                    inst[i][j].sel1 = 1; 
                    inst[i][j].valid = 1;
                    //处理该操作带来的后果
                    EleNodePointer[it->c]->setTime(i + DELAY);
                    int remain = EleNodePointer[it->c]->getToDo();
                    if (remain == 1)
                    {
                        EleNodePointer[it->c]->setValid(1);
                        newly_valid.push_back(it->c);
                    }
                    EleNodePointer[it->c]->setToDo(remain - 1);
                        
                    if (ok1 == 1) ocp[i]->push_back(it->rs);
                    ocp[i]->push_back(it->c);
                    //在pool中删除该操作
                    it = pool.erase(it);
                    --it;
                    //进行下一个j
                    break;
                }
            }
            else //是ms
            {
//                //判定操作数是否ready
//                if ((EleNodePointer[it->c]->getTime() > (i + 1)) || (EleNodePointer[it->rt]->getTime() > i) || (EleNodePointer[it->rs]->getTime() > i))
//                    continue;
                //判定rs和rt是否冲突
                if (it->rs % NBANK == it->rt % NBANK) //冲突啦，需要3个连续的slot：i i+1 i+2
                {
                    //判定操作数是否ready
                    if ((EleNodePointer[it->c]->getTime() > (i + 2)) || (EleNodePointer[it->rt]->getTime() > i) || (EleNodePointer[it->rs]->getTime() > (i + 1)))
                        continue;
                    //检查rt能否放入i
                    int ok1 = check(it->rt, ocp[i]);
                    if (!ok1) continue;
                    //检查rs能否放入i+1
                    int ok2 = check(it->rs, ocp[i + 1]);
                    if (!ok2) continue;
                    //检查c能否放入i+2
                    int ok3 = check(it->c, ocp[i + 2]);
                    if (!ok3) continue;
                    //满足条件！将该操作调度到i和i+1和i+2的PE j上
                    inst[i][j].rt = it->rt;
                    inst[i][j].op = 0; //乘法
                    inst[i][j].sel1 = 1; //输入rt
                    inst[i][j].valid = 1;
                    inst[i + 1][j].rs = it->rs;
                    inst[i + 1][j].op = 0; //乘法
                    inst[i + 1][j].sel1 = 0; //未输入rt
                    inst[i + 1][j].valid = 1;
                    inst[i + 2][j].rs = it->c;
                    inst[i + 2][j].op = 2; //减法
                    inst[i + 2][j].valid = 1;
                    //处理该操作带来的后果
                    EleNodePointer[it->c]->setTime(i + 2 + DELAY);
                    int remain = EleNodePointer[it->c]->getToDo();
                    if (remain == 1) //是写操作数的最后一次操作
                    {
                        EleNodePointer[it->c]->setValid(1);
                        newly_valid.push_back(it->c);
                    }
                    EleNodePointer[it->c]->setToDo(remain - 1);

                    if (ok1 == 1) ocp[i]->push_back(it->rt);
                    if (ok2 == 1) ocp[i + 1]->push_back(it->rs);
                    ocp[i + 2]->push_back(it->c);
                    //在pool中删除该操作
                    it = pool.erase(it);
                    --it;
                    //进行下一个j
                    break;
                }
                else //没有冲突，只需要2个slot: i i+1
                {
                    //判定操作数是否ready
                    if ((EleNodePointer[it->c]->getTime() > (i + 1)) || (EleNodePointer[it->rt]->getTime() > i) || (EleNodePointer[it->rs]->getTime() > i))
                        continue;
                    //检查rt能否放入i
                    int ok1 = check(it->rt, ocp[i]);
                    if (!ok1) continue;
                    //检查rs能否放入i
                    int ok2 = check(it->rs, ocp[i]);
                    if (!ok2) continue;
                    //检查c能否放入i+1
                    int ok3 = check(it->c, ocp[i + 1]);
                    if (!ok3) continue;
                    //满足条件！将该操作调度到i和i+1的PE j上
                    inst[i][j].rs = it->rs;
                    inst[i][j].rt = it->rt;
                    inst[i][j].op = 0; //乘法
                    inst[i][j].sel1 = 1; //输入rt
                    inst[i][j].valid = 1;
                    inst[i + 1][j].rs = it->c;
                    inst[i + 1][j].op = 2; //减法
                    inst[i + 1][j].valid = 1;
                    //处理该操作带来的后果
                    EleNodePointer[it->c]->setTime(i + 1 + DELAY);
                    int remain = EleNodePointer[it->c]->getToDo();
                    if (remain == 1)
                    {
                        EleNodePointer[it->c]->setValid(1);
                        newly_valid.push_back(it->c);
                    }
                    EleNodePointer[it->c]->setToDo(remain - 1);

                    if (ok1 == 1) ocp[i]->push_back(it->rt);
                    if (ok2 == 1) ocp[i]->push_back(it->rs);
                    ocp[i + 1]->push_back(it->c);
                    //在pool中删除该操作
                    it = pool.erase(it);
                    --it;
                    //进行下一个j
                    break;
                }

            }

        }
        
    }
}

void printInst(const InstPack inst[][NPE], const int start, const int end){
    cout << "this is the instruction from " << start << " to " << end << endl;
    for(int i = start; i < end; i++){
        cout << i << ":";
        for (int j = 0; j < NPE; j++){
            cout << "\t(" << inst[i][j].rs << ", " << inst[i][j].rt << ", " << inst[i][j].op
            << ", " << inst[i][j].sel1 << ", " << inst[i][j].valid << ")";
        }
        cout << endl;
    }
}

void addWl(EleNode* EleNodePointer[], std::vector<int>& newly_valid, std::vector<OpPack>& wl) {
    for (int ele : newly_valid) {
        std::vector<int> child = EleNodePointer[ele]->getChild();
        for (auto it = child.begin(); it != child.end(); ++it) {
            std::vector<OpPack>& pool = EleNodePointer[*it]->pool;
            for (auto p = pool.begin(); p != pool.end(); ++p) {
                if (p->op == 1) {
                    //检查除法
                    if ((p->rs == ele) && (p == pool.begin())) {
                        wl.push_back(*p);
                        p = pool.erase(p);
                        --p;
                    }
                }
                else {
                    //检查ms
                    if (p->rs == ele) {
                        if (EleNodePointer[p->rt]->getValid()) {
                            wl.push_back(*p);
                            p = pool.erase(p);
                            --p;
                        }
                    }
                    else if (p->rt == ele) {
                        if (EleNodePointer[p->rs]->getValid()) {
                            wl.push_back(*p);
                            p = pool.erase(p);
                            --p;
                        }
                    }
                }

                if (pool.size() == 1)
                {
                    //检查一下最后的除法可不可以做
                    if (((p + 1)->op == 1) && EleNodePointer[(p + 1)->rs]->getValid()) //最后一个操作就是除法，且rs已经ready
                    {
                        ++p;
                        wl.push_back(*p);
                        p = pool.erase(p);
                        --p;
                    }
                }
            }
        }
//            std::cout << "waiting list is: " << endl;
//            for (const auto& element : wl) {
//                std::cout << "<" << element.rs << "," << element.rt << "," << element.c << "," << element.op << "> " << endl;;
//            }
    }
//        std::cout << ele << " returned!\n";
}
    
int simulate(const InstPack inst[][NPE], std::vector<float>& Ax, const std::vector<int>& Ai, int time) {
    for (int i = 0; i < time; i++) {
        for (int j = 0; j < NPE; j++) {
            if (!inst[i][j].valid)
                continue;
            if ((inst[i][j].op == 3) && (inst[i][j].sel1 == 1)) //是除法的第一个周期
            {
                if ((inst[i + 1][j].op == 3) && (inst[i + 1][j].sel1 == 0)) //冲突情况
                {
                    float A = Ax[inst[i + 1][j].rs];
                    float B = Ax[inst[i][j].rt];
                    // A / B
                    if (B == 0)
                    {
                        std::cout << "divided by zero in inst[" << i << "][" << j << "]\n";
                        return -1;
                    }
                    Ax[inst[i + 1][j].rs] = A / B;
                    std::cout << "time: " << i << "\tPE: " << j << "\top: ";
                    std::cout << A << " / " << B << " = " << Ax[inst[i + 1][j].rs] << std::endl;
                }
                else //未冲突情况
                {
                    float A = Ax[inst[i][j].rs];
                    float B = Ax[inst[i][j].rt];
                    // A / B
                    if (B == 0)
                    {
                        std::cout << "divided by zero in inst[" << i << "][" << j << "]\n";
                        return -1;
                    }
                    Ax[inst[i][j].rs] = A / B;
                    std::cout << "time: " << i << "\tPE: " << j << "\top: ";
                    std::cout << A << " / " << B << " = " << Ax[inst[i][j].rs] << std::endl;
                }
            }
            if ((inst[i][j].op == 0) && (inst[i][j].sel1 == 1))//是乘法的第一周期
            {
                if (inst[i + 1][j].op == 2)
                {
                    float A = Ax[inst[i][j].rs];
                    float B = Ax[inst[i][j].rt];
                    float C = Ax[inst[i + 1][j].rs];
                    Ax[inst[i + 1][j].rs] = C - A * B;
                    std::cout << "time: " << i << "\tPE: " << j << "\top: ";
                    std::cout << C << " - " << A << " * " << B << " = " << Ax[inst[i + 1][j].rs] << endl;
                }
                else if (inst[i + 1][j].op == 0) //两个乘操作冲突
                {
                    float A = Ax[inst[i + 1][j].rs];
                    float B = Ax[inst[i][j].rt];
                    float C = Ax[inst[i + 2][j].rs];
                    Ax[inst[i + 2][j].rs] = C - A * B;
                    std::cout << "time: " << i << "\tPE: " << j << "\top: ";
                    std::cout << C << " - " << A << " * " << B << " = " << Ax[inst[i + 2][j].rs] << endl;
                }  
                
            }
        }
    }
    return 0;
}
    
void compareGolden(const std::vector<float>& g, const std::vector<float>& my, const int nnz) {
    int correct = 0;
    int wrong = 0;
    for (int i = 0; i < nnz; i++) {
        if (g[i] == 0) {
            std::cout << "g[i] = 0, my = " << my[i] << std::endl;
        }
        else if (abs((my[i] - g[i]) / g[i]) <= 0.001) correct++;
        else{
            std::cout << "position " << i << " is wrong, the golden value is " << g[i] << " , my value is " << my[i] << endl;
            wrong++;
        }
    }
    cout << "correct = " << correct << " , wrong = " << wrong << endl;
}


