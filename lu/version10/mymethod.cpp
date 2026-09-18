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
    size_t start_value = static_cast<size_t>(start);
    size_t end_value = static_cast<size_t>(end);
    if (end_value >= original.size() || start_value > end_value) {
        std::cout << "Invalid range\n";
        return subVector;
    }

    for (unsigned i = start_value; i <= end_value; ++i) {
        subVector.push_back(original[i]);
    }

    return subVector;
}

std::vector<float> extractSubVectorFloat(const std::vector<float>& original, int start, int end) {
    std::vector<float> subVector;
    size_t start_value = static_cast<size_t>(start);
    size_t end_value = static_cast<size_t>(end);
    if (end_value >= original.size() || start_value > end_value) {
        std::cout << "Invalid range\n";
        return subVector;
    }

    for (unsigned i = start_value; i <= end_value; ++i) {
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
    std::cout << "ERROR: Failed to find row position for " << row << std::endl;
    return -1; // 如果未找到，返回-1表示未找到
}


int fillIn(
    const std::vector<float>& Ax, // 非零元素
    const std::vector<int>& Ai, // 索引
    const std::vector<int>& Ap, // 指针
    const int n, //order
    std::vector<float>& Ax_fill, //非零元素after fill in
    std::vector<int>& Ai_fill, // 索引after fill in
    std::vector<int>& Ap_fill,  //指针after fill in
    std::vector<int>& Ad_fill  //对角元素指针after fill in
){
    int row;
    
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

//        std::cout << "handling column " << k;

//        std::cout << "\nSubAi: ";
//        for (int i : subAi) 
//        {
//            std::cout << i << " ";
//        }

//        std::cout << "\nSubAx: ";
//        for (float i : subAx) 
//        {
//            std::cout << i << " ";
//        }

        while (!myQue.empty())
        {
            row = myQue.front();
//            cout << "Analyzing A(" << row << "," << k << ")";

            if (row < k) //需要检查左列，注意左列是已经完成fill in填充的
           {
//                cout << "\tChecked!\n";
                addMissingElements(Ai_fill, Ad_fill[row] + 1, Ap_fill[row + 1] - 1, subAi, subAx, myQue);
                //addMissingElementsFalse(Ai_fill, Ad_fill[row] + 1, Ap_fill[row + 1] - 1, subAi, subAx, myQue);  
            }
            myQue.erase(myQue.begin());
        }

        // 创建一个包含原始位置和值的 Pair 结构体的向量
        std::vector<Pair> pairs;
        for (unsigned int i = 0; i < subAi.size(); ++i) {
            pairs.push_back({static_cast<int>(i), subAi[i]});
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
//        std::cout << "Sorted Ai: ";
//        for (int val : Ai_new) 
//        {
//            std::cout << val << " ";
//        }
//        std::cout << "\n";

//        std::cout << "Corresponding Ax: ";
//        for (float val : Ax_new) 
//        {
//            std::cout << val << " ";
//        }
//        std::cout << "\n";

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
    size_t start_value = static_cast<size_t>(start);
    size_t end_value = static_cast<size_t>(end);
    if (start_value >= vec.size() || end_value >= vec.size() || start_value > end_value) {
        std::cerr << "Invalid range." << std::endl;
        return 0;
    }

    // 在指定范围内寻找值为 row 的元素
    for (unsigned i = start_value; i <= end_value; ++i) {
        if (vec[i] == row) {
            *p_location = i;
            return 1;  // 找到了
        }
    }

    return 0;  // 没有找到
}

int buildGraph(EleNode* EleNodePointer[], int n, const std::vector<int>& Ai, const std::vector<int>& Ap, const std::vector<int>& Ad, std::vector<int>& remain) {
    int ele = 0;
    for (int k = 0; k < n; k++) {
        for (int p = Ap[k]; p < Ap[k + 1]; p ++, ele++) {
            int row = Ai[p];
//            cout << "this is ele : " << ele << endl;
//            cout << "col is " << k << ", row is " << row << endl;
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
                        //OpPack newpair = {j, location, ele, 0, diag}; // A = j, B = location, C = ele, diag标志是对角线，调度的时候需检查to_do==1
                        OpPack newpair;
                        newpair.rs = j;
                        newpair.rt = location;
                        newpair.rd = ele;
                        newpair.op = 0;
//                        if (p == Ad[k])
//                            newpair.diag = 1;
                        EleNodePointer[ele]->pool.push_back(newpair);
                    }
                }

                if (p > Ad[k]) { //下三角元素额外处理
//                    cout << ele << " divided\n";
                    valid = 0;
                    to_do ++;
                    EleNodePointer[Ad[k]]->addChild(ele);  //给依赖对象对角元素增加child
                    //OpPack newpair = {-1, Ad[k], ele, 1, 0}; //C = ele, A = Ad[k]
                    OpPack newpair;
                    newpair.rt = Ad[k];
                    newpair.rd = ele;
                    newpair.op = 1;
                    EleNodePointer[ele]->pool.push_back(newpair);
                }
                EleNodePointer[ele]->setValid(valid);
                EleNodePointer[ele]->setToDo(to_do);

                //添加remain
                if (!valid)
                    remain.push_back(ele);
            }

//            cout << ele << " returned\n";
        }
    }
    return 0;
}

int initialWl(EleNode* EleNodePointer[], int nnz, std::vector<OpPack>& wl) {
    for (int ele = 0; ele < nnz; ele++) {
        if (EleNodePointer[ele]->getValid()) {
//            cout << "the valid element is " << ele << endl;
            std::vector<int> child = EleNodePointer[ele]->getChild();

            for (int childIndex : child) {
                EleNode* childEleNode = EleNodePointer[childIndex];
                std :: vector<OpPack>& pool = childEleNode->pool;
                for (auto p = pool.begin(); p != pool.end(); ) {
                    if (p->op == 1) {
                        //检查除法
                        if ((p->rt == ele) && (p == pool.begin())) {
                            wl.push_back(*p);
                            p = pool.erase(p);
                        }
                        else ++p;
                    }
                    else {
                        //检查ms
                        if ((p->rs == ele && EleNodePointer[p->rt]->getValid()) || 
                            (p->rt == ele && EleNodePointer[p->rs]->getValid())) {
                            wl.push_back(*p);
                            p = pool.erase(p);
                        }
                        else ++p;
                    }
                }
                if (pool.size() == 1 && pool.back().op == 1 && EleNodePointer[pool.back().rt]->getValid()) {
                    //检查最后的除法是否可以做
                    wl.push_back(pool.back());
                    pool.pop_back();
                }
            }
/*            for (std::vector<int>::iterator it = child.begin(); it != child.end(); ++it) {
                std::vector<OpPack>& pool = EleNodePointer[*it]->pool;
                for (std::vector<OpPack>::iterator p = pool.begin(); p != pool.end(); ++p) {
                    if (p->op == 1) {
                        //检查除法
                        if ((p->rt == ele) && (p == pool.begin())) { //为了保证除法永远在ms做完了之后再做
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
                        if (((p + 1)->op == 1) && EleNodePointer[(p + 1)->rt]->getValid()) //最后一个操作就是除法，且rt已经ready
                        {
                            ++p;
                            wl.push_back(*p);
                            p = pool.erase(p);
                            --p;
                        }
                    }
                }
            }
            */
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
    for (unsigned int i = 0; i < pool.size(); ++i) {
        if (pool[i].rd == c) {
            return 1;
        }
    }
    return 0; // 如果未找到，返回0表示未找到
}

void addOkToDo(std::vector<OpPack>& wl, std::vector<OpPack>& pool) {
    for (std::vector<OpPack>::iterator it = wl.begin(); it != wl.end(); ++it) {
        //要求：新加入的pair的c不能与pool中原有的c重合，c就是写回地址rd
        int found = findC(pool, it->rd);
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

void schedule(InstPack** inst, std::vector<int>* ocp_rd[], std::vector<int>* ocp_wr[], EleNode* EleNodePointer[], std::vector<OpPack>& pool, int i, std::vector<int>& newly_valid, std::vector<int>& remain_node) {
    for (int j = 0; j < NPE; j++) {
        if (inst[i][j].op != 0) //已经被填充了，跳过
            continue;
        //找到一个空位，开始在pool中逐个寻找合适的元素，直到pool结尾
        for (std::vector<OpPack>::iterator it = pool.begin(); it != pool.end(); ++it) {
            //首先判断it的操作类型
            if (it->op) //是除法
            {
                //判定除数和被除数是否冲突 rd rt
                if (it->rd % NBANK == it->rt % NBANK) //冲突啦，需要两个连续的slot：i i+1
                {
                    //判定操作数是否ready
                    if ((EleNodePointer[it->rd]->getTime() > (i + 1)) || (EleNodePointer[it->rt]->getTime() > i))
                        continue;
                    //检查rt能否放入i
                    int ok1 = check(it->rt, ocp_rd[i]);
                    if (!ok1) continue;
                    //检查rd能否放入i+1
                    int ok2 = check(it->rd, ocp_rd[i + 1]);
                    if (!ok2) continue;
                    int ok3 = check(it->rd, ocp_wr[i + LAT_2]);
                    if (!ok3) continue;
                    //满足条件！将该操作调度到i和i+1的PE j上
                    inst[i][j].rt = it->rt;
                    inst[i][j].op = 2;
                    //inst[i][j].sel2 = 1;
                    //inst[i][j].valid = 1;

                    inst[i + 1][j].rs = it->rd;
                    inst[i + 1][j].op = 3;
                    //inst[i + 1][j].sel3 = 1; //rd写入
                    //inst[i + 1][j].valid = 1;
                    //处理该操作带来的后果
                    EleNodePointer[it->rd]->setTime(i + 1 + LAT_2);
                    int remain = EleNodePointer[it->rd]->getToDo();
                    if (remain == 1)
                    {
                        EleNodePointer[it->rd]->setValid(1);
                        newly_valid.push_back(it->rd);

                        //处理remain
                        for (vector<int>::iterator iter = remain_node.begin(); iter != remain_node.end(); iter++) {
                            if (*iter == it->rd) {
                                remain_node.erase(iter);
                                break;
                            }
                        }

                    }
                    EleNodePointer[it->rd]->setToDo(remain - 1);
                        
                    if (ok1 == 1) ocp_rd[i]->push_back(it->rt);
                    if (ok2 == 1) ocp_rd[i + 1]->push_back(it->rd);
                    ocp_wr[i + LAT_2]->push_back(it->rd);
                    //在pool中删除该操作
                    it = pool.erase(it);
                    --it;
                    //进行下一个j
                    break;
                }
                else //没有冲突，只需要一个slot: i
                {
                    //判定操作数是否ready
                    if ((EleNodePointer[it->rd]->getTime() > i) || (EleNodePointer[it->rt]->getTime() > i))
                        continue;
                    //检查rt能否放入i
                    int ok1 = check(it->rt, ocp_rd[i]);
                    if (!ok1) continue;
                    //检查c能否放入i
                    int ok2 = check(it->rd, ocp_rd[i]);
                    if (!ok2) continue;
                    int ok3 = check(it->rd, ocp_wr[i + LAT_1]);
                    if (!ok3) continue;
                    //满足条件！将该操作调度到i的PE j上
                    inst[i][j].rt = it->rt;
                    inst[i][j].rs = it->rd;
                    inst[i][j].op = 1;
                    //inst[i][j].sel2 = 1; 
                    //inst[i][j].sel3 = 1; 
                    //inst[i][j].valid = 1;
                    //处理该操作带来的后果
                    EleNodePointer[it->rd]->setTime(i + LAT_1 + 1);
                    int remain = EleNodePointer[it->rd]->getToDo();
                    if (remain == 1)
                    {
                        EleNodePointer[it->rd]->setValid(1);
                        newly_valid.push_back(it->rd);

                        //处理remain
                        for (vector<int>::iterator iter = remain_node.begin(); iter != remain_node.end(); iter++) {
                            if (*iter == it->rd) {
                                remain_node.erase(iter);
                                break;
                            }
                        }
                    }
                    EleNodePointer[it->rd]->setToDo(remain - 1);
                        
                    if (ok1 == 1) ocp_rd[i]->push_back(it->rt);
                    if (ok2 == 1) ocp_rd[i]->push_back(it->rd);
                    ocp_wr[i + LAT_1]->push_back(it->rd);
                    //在pool中删除该操作
                    it = pool.erase(it);
                    --it;
                    //进行下一个j
                    break;
                }
            }
            else //是ms
            {
                //情况5，rs,rt,rd全部冲突
                if ((it->rd % NBANK == it->rs % NBANK) && (it->rd % NBANK == it->rt % NBANK)) //冲突啦，需要3个连续的slot：i i+1 i+2
                {
                    //判定操作数是否ready
                    if ((EleNodePointer[it->rd]->getTime() > (i + 2)) || (EleNodePointer[it->rt]->getTime() > i) || (EleNodePointer[it->rs]->getTime() > (i + 1)))
                        continue;
                    //检查rt能否放入i
                    int ok1 = check(it->rt, ocp_rd[i]);
                    if (!ok1) continue;
                    //检查rs能否放入i+1
                    int ok2 = check(it->rs, ocp_rd[i + 1]);
                    if (!ok2) continue;
                    //检查rd能否放入i+2
                    int ok3 = check(it->rd, ocp_rd[i + 2]);
                    if (!ok3) continue;
                    int ok4 = check(it->rd, ocp_wr[i + LAT_9]);
                    if (!ok4) continue;
                    //满足条件！将该操作调度到i和i+1和i+2的PE j上
                    inst[i][j].rt = it->rt;
                    inst[i][j].op = 9; //ms
                    //inst[i][j].sel2 = 1; //输入rt
                    //inst[i][j].valid = 1;

                    inst[i + 1][j].rs = it->rs;
                    inst[i + 1][j].op = 10; //ms
                    //inst[i + 1][j].sel1 = 1; //输入rs
                    //inst[i + 1][j].valid = 1;

                    inst[i + 2][j].rd = it->rd;
                    inst[i + 2][j].op = 11; //ms
                    //inst[i + 2][j].sel3 = 1; //输入rd
                    //inst[i + 2][j].valid = 1;
                    //处理该操作带来的后果
                    EleNodePointer[it->rd]->setTime(i + LAT_9 + 1);
                    int remain = EleNodePointer[it->rd]->getToDo();
                    if (remain == 1) //是写操作数的最后一次操作
                    {
                        EleNodePointer[it->rd]->setValid(1);
                        newly_valid.push_back(it->rd);

                        //处理remain
                        for (vector<int>::iterator iter = remain_node.begin(); iter != remain_node.end(); iter++) {
                            if (*iter == it->rd) {
                                remain_node.erase(iter);
                                break;
                            }
                        }
                    }
                    EleNodePointer[it->rd]->setToDo(remain - 1);

                    if (ok1 == 1) ocp_rd[i]->push_back(it->rt);
                    if (ok2 == 1) ocp_rd[i + 1]->push_back(it->rs);
                    if (ok3 == 1) ocp_rd[i + 2]->push_back(it->rd);
                    ocp_wr[i + LAT_9]->push_back(it->rd);
                    //在pool中删除该操作
                    it = pool.erase(it);
                    --it;
                    //进行下一个j
                    break;
                }
                //判定rd和rs冲突或rd和rt是否冲突，情况3，4
                else if ((it->rd % NBANK == it->rs % NBANK) || (it->rd % NBANK == it->rt % NBANK)) //冲突啦，需要2个连续的slot：i i+1
                {
                    //判定操作数是否ready
                    if ((EleNodePointer[it->rd]->getTime() > (i + 1)) || (EleNodePointer[it->rt]->getTime() > i) || (EleNodePointer[it->rs]->getTime() > i))
                        continue;
                    //检查rt能否放入i
                    int ok1 = check(it->rt, ocp_rd[i]);
                    if (!ok1) continue;
                    //检查rs能否放入i
                    int ok2 = check(it->rs, ocp_rd[i]);
                    if (!ok2) continue;
                    //检查rd能否放入i+1
                    int ok3 = check(it->rd, ocp_rd[i + 1]);
                    if (!ok3) continue;
                    int ok4 = check(it->rd, ocp_wr[i + LAT_7]);
                    if (!ok4) continue;
                    //满足条件！将该操作调度到i和i+1的PE j上
                    inst[i][j].rs = it->rs;
                    inst[i][j].rt = it->rt;
                    inst[i][j].op = 7; //ms
                    //inst[i][j].sel1 = 1; //输入rs
                    //inst[i][j].sel2 = 1; //输入rt
                    //inst[i][j].valid = 1;
                    
                    inst[i + 1][j].rd = it->rd;
                    inst[i + 1][j].op = 8; //ms
                    //inst[i + 1][j].sel3 = 1; //输入rd
                    //inst[i + 1][j].valid = 1;
                    //处理该操作带来的后果
                    EleNodePointer[it->rd]->setTime(i + LAT_7 + 1);
                    int remain = EleNodePointer[it->rd]->getToDo();
                    if (remain == 1) //是写操作数的最后一次操作
                    {
                        EleNodePointer[it->rd]->setValid(1);
                        newly_valid.push_back(it->rd);

                        //处理remain
                        for (vector<int>::iterator iter = remain_node.begin(); iter != remain_node.end(); iter++) {
                            if (*iter == it->rd) {
                                remain_node.erase(iter);
                                break;
                            }
                        }
                    }
                    EleNodePointer[it->rd]->setToDo(remain - 1);

                    if (ok1 == 1) ocp_rd[i]->push_back(it->rt);
                    if (ok2 == 1) ocp_rd[i]->push_back(it->rs);
                    if (ok3 == 1) ocp_rd[i + 1]->push_back(it->rd);
                    ocp_wr[i + LAT_7]->push_back(it->rd);
                    //在pool中删除该操作
                    it = pool.erase(it);
                    --it;
                    //进行下一个j
                    break;
                }
                //判定rs和rt是否冲突，情况2
                else if (it->rt % NBANK == it->rs % NBANK) //冲突啦，需要2个连续的slot：i i+1
                {
                    //判定操作数是否ready
                    if ((EleNodePointer[it->rd]->getTime() > (i + 1)) || (EleNodePointer[it->rt]->getTime() > i) || (EleNodePointer[it->rs]->getTime() > (i + 1)))
                        continue;
                    //检查rt能否放入i
                    int ok1 = check(it->rt, ocp_rd[i]);
                    if (!ok1) continue;
                    //检查rs能否放入i + 1
                    int ok2 = check(it->rs, ocp_rd[i + 1]);
                    if (!ok2) continue;
                    //检查rd能否放入i+1
                    int ok3 = check(it->rd, ocp_rd[i + 1]);
                    if (!ok3) continue;
                    int ok4 = check(it->rd, ocp_wr[i + LAT_5]);
                    if (!ok4) continue;
                    //满足条件！将该操作调度到i和i+1的PE j上
                    inst[i][j].rt = it->rt;
                    inst[i][j].op = 5; //ms
                    //inst[i][j].sel2 = 1; //输入rt
                    //inst[i][j].valid = 1;
                    
                    inst[i + 1][j].rs = it->rs;
                    inst[i + 1][j].rd = it->rd;
                    inst[i + 1][j].op = 6; //ms
                    //inst[i + 1][j].sel1 = 1; //输入rs
                    //inst[i + 1][j].sel3 = 1; //输入rd
                    //inst[i + 1][j].valid = 1;
                    //处理该操作带来的后果
                    EleNodePointer[it->rd]->setTime(i + LAT_5 + 1);
                    int remain = EleNodePointer[it->rd]->getToDo();
                    if (remain == 1) //是写操作数的最后一次操作
                    {
                        EleNodePointer[it->rd]->setValid(1);
                        newly_valid.push_back(it->rd);

                        //处理remain
                        for (vector<int>::iterator iter = remain_node.begin(); iter != remain_node.end(); iter++) {
                            if (*iter == it->rd) {
                                remain_node.erase(iter);
                                break;
                            }
                        }
                    }
                    EleNodePointer[it->rd]->setToDo(remain - 1);

                    if (ok1 == 1) ocp_rd[i]->push_back(it->rt);
                    if (ok2 == 1) ocp_rd[i + 1]->push_back(it->rs);
                    if (ok3 == 1) ocp_rd[i + 1]->push_back(it->rd);
                    ocp_wr[i + LAT_5]->push_back(it->rd);
                    //在pool中删除该操作
                    it = pool.erase(it);
                    --it;
                    //进行下一个j
                    break;
                }
                else //没有冲突情况1，只需要1个slot: i
                {
                    //判定操作数是否ready
                    if ((EleNodePointer[it->rd]->getTime() > i) || (EleNodePointer[it->rt]->getTime() > i) || (EleNodePointer[it->rs]->getTime() > i))
                        continue;
                    //检查rt能否放入i
                    int ok1 = check(it->rt, ocp_rd[i]);
                    if (!ok1) continue;
                    //检查rs能否放入i
                    int ok2 = check(it->rs, ocp_rd[i]);
                    if (!ok2) continue;
                    //检查rd能否放入i
                    int ok3 = check(it->rd, ocp_rd[i]);
                    if (!ok3) continue;
                    int ok4 = check(it->rd, ocp_wr[i + LAT_4]);
                    if (!ok4) continue;
                    //满足条件！将该操作调度到i的PE j上
                    inst[i][j].rs = it->rs;
                    inst[i][j].rt = it->rt;
                    inst[i][j].rd = it->rd;
                    inst[i][j].op = 4; //ms
                    //inst[i][j].sel1 = 1; //输入rs
                    //inst[i][j].sel2 = 1; //输入rt
                    //inst[i][j].sel3 = 1; //输入rd
                    //inst[i][j].valid = 1;
                    //处理该操作带来的后果
                    EleNodePointer[it->rd]->setTime(i + LAT_4 + 1);
                    int remain = EleNodePointer[it->rd]->getToDo();
                    if (remain == 1)
                    {
                        EleNodePointer[it->rd]->setValid(1);
                        newly_valid.push_back(it->rd);

                        //处理remain
                        for (vector<int>::iterator iter = remain_node.begin(); iter != remain_node.end(); iter++) {
                            if (*iter == it->rd) {
                                remain_node.erase(iter);
                                break;
                            }
                        }
                    }
                    EleNodePointer[it->rd]->setToDo(remain - 1);

                    if (ok1 == 1) ocp_rd[i]->push_back(it->rt);
                    if (ok2 == 1) ocp_rd[i]->push_back(it->rs);
                    if (ok3 == 1) ocp_rd[i]->push_back(it->rd);
                    ocp_wr[i + LAT_4]->push_back(it->rd);
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

void printInst(InstPack** inst, const int start, const int end){
    std::cout << "this is the instruction from " << start << " to " << end << endl;
    for(int i = start; i < end; i++){
        std::cout << i << ":";
        for (int j = 0; j < NPE; j++){
            cout << "\t(" << inst[i][j].rs << ", " << inst[i][j].rt << ", " << inst[i][j].rd << ", " << inst[i][j].op << ")";
        }
        std::cout << std::endl;
    }
    std::cout << "Print Inst Finished!\n";
}

void addWl(EleNode* EleNodePointer[], std::vector<int>& newly_valid, std::vector<OpPack>& wl) {
    for (int ele : newly_valid) {
        std::vector<int> child = EleNodePointer[ele]->getChild();

        for (int childIndex : child) {
            EleNode* childEleNode = EleNodePointer[childIndex];
            std :: vector<OpPack>& pool = childEleNode->pool;
            for (auto p = pool.begin(); p != pool.end(); ) {
                if (p->op == 1) {
                    //检查除法
                    if ((p->rt == ele) && (p == pool.begin())) {
                        wl.push_back(*p);
                        p = pool.erase(p);
                    }
                    else ++p;
                }
                else {
                    //检查ms
                    if ((p->rs == ele && EleNodePointer[p->rt]->getValid()) || 
                        (p->rt == ele && EleNodePointer[p->rs]->getValid())) {
                        wl.push_back(*p);
                        p = pool.erase(p);
                    }
                    else ++p;
                }
            }
            if (pool.size() == 1 && pool.back().op == 1 && EleNodePointer[pool.back().rt]->getValid()) {
                //检查最后的除法是否可以做
                wl.push_back(pool.back());
                pool.pop_back();
            }
        }
    }
}

int evictList(const std::vector<OpPack>& pool, std::vector<std::vector<OpPack>*>& nodes, const std::vector<int>& node) {
    for (const auto& op : pool) {
        auto it = std::find(node.begin(), node.end(), op.rd);
        if (it == node.end()) {
            std::cout << "ERROR: fail to evict " << op.rd << " in the list!\n";
            return -1;
        }

        size_t i = std::distance(node.begin(), it);
        nodes[i]->emplace_back(op);
    }
    return 0;
}

void evictTree(EleNode* EleNodePointer[], std::vector<std::vector<OpPack>*>& nodes, const std::vector<int>& node, const int n) {
    for (int i = 0; i < n; i++) {
        int ele = node[i]; //元素
        std::vector<OpPack> pool = EleNodePointer[ele]->pool;
        for (OpPack p : pool) {
            nodes[i]->push_back(p);
        }
    }
}

bool compareByPriority(int a, int b, const std::vector<int>& pri) {
    return pri[a] > pri[b];
}

void sortByPriority(std::vector<int>& node, std::vector<std::vector<OpPack>*>& nodes, const std::vector<int>& pri) {
    // 创建一个临时向量，存储索引值
    std::vector<size_t> indices(node.size());
    for (size_t i = 0; i < node.size(); ++i) {
        indices[i] = i;
    }

    // 根据优先级从大到小排序 indices
    std::sort(indices.begin(), indices.end(), [&](size_t a, size_t b) {
        return pri[a] > pri[b];
    });

    // 使用排序后的 indices 更新原始的 node 和 nodes
    std::vector<int> sortedNode(node.size());
    std::vector<std::vector<OpPack>*> sortedNodes(node.size());
    for (size_t i = 0; i < node.size(); ++i) {
        sortedNode[i] = node[indices[i]];
        sortedNodes[i] = nodes[indices[i]];
    }
    node = sortedNode;
    nodes = sortedNodes;
    std::cout << std::endl;
}


void addPri(EleNode* EleNodePointer[], std::vector<int>& pri, std::vector<std::vector<OpPack>*>& nodes, std::vector<int>& node, const int n) {
    for (int i = n - 1; i >= 0; i--) {
        int ele = node[i]; //元素
        int self_op = nodes[i]->size();
        pri[i] += self_op;
        std::vector<int> childVec = EleNodePointer[ele]->getChild();
        if (childVec.size()) //有child
        {
            int j;
            for (int child : childVec) //逐个检查child是否在node中
            {
                for (j = i; j < n; j++) {
                    if (node[j] == child)
                        break;
                }
                if (j < n) //找到了
                {
                    pri[i] += pri[j];
                }
            }
        }     
    }
}

void checkOnlyDiv(std::vector<bool>& only_div, std::vector<std::vector<OpPack>*>& nodes, const int n_node)
{
    for (int i = 0; i < n_node; i++)
    {
        if (nodes[i]->size() == 1)
            only_div[i] = 1;
    }
}

void schedule2(InstPack** inst, std::vector<int>* ocp_rd[], std::vector<int>* ocp_wr[], EleNode* EleNodePointer[], 
                std::vector<std::vector<OpPack>*>& nodes, const std::vector<int>& node, const int n, 
                const int i, const std::vector<bool>& only_div, std::vector<bool>& ok_to_sub, std::vector<bool>& ok_to_wb, 
                std::vector<int>& ok_to_wb_time, std::vector<int>& regC_ready_time, int* p_current) {
    // ElenodePointer负责提供readytime和valid的信息
    // 操作从nodes中获得

    for (int j = 0; j < n; j++) // 只对前n个PE进行调度，后面n~NPE的PE是空的
    {
        if (EleNodePointer[node[j]]->getValid()) //该元素已经操作完成
            continue;
        if (inst[i][j].op != 0)   // 已经被填充过了，跳过
            continue;
        
        if (ok_to_sub[j] == 1) 
        {
            if (regC_ready_time[j] > i) //受到mac操作影响，regC/mac_result还不能读。
                continue;
            // 检查读出被减数C是否会有冲突
            int ok1 = check(node[j], ocp_rd[i]);
            if (!ok1) continue;
            // 没有冲突，可以做减法。将该操作调度到i的PE j上
            // 没有剩下的除法时，直接写回
            if (!nodes[j]->size()) {
                //检查写回是否会有冲突        
                int ok2 = check(node[j], ocp_wr[i + 4]);
                if (!ok2) continue;
                //没有冲突，可以写回。将该操作调度到i的PE j上
                inst[i][j].rs = node[j];
                if (regC_ready_time[j] == i) //mac结果直接连
                    inst[i][j].op = 22;
                else //减数从regC中来
                    inst[i][j].op = 23;
                // 处理该操作带来的后果
                EleNodePointer[node[j]]->setTime(i + 5);
                EleNodePointer[node[j]]->setValid(1);
                (*p_current)--;

                ocp_wr[i + 4]->push_back(node[j]);
            }
            else
            // 接下来还有除法，减法结果保存在regF中
            {
                inst[i][j].rs = node[j];
                if (regC_ready_time[j] == i) //mac结果直接连
                    inst[i][j].op = 17;
                else //减数从regC中来
                    inst[i][j].op =18;
            }

            if (ok1 == 1) ocp_rd[i]->push_back(node[j]);
            //不用在nodes中删除操作
            ok_to_sub[j] = 0;
            continue;
        }

        // 找到一个空位j，查看node[j]对应的第一个操作是否可以做
        std::vector<OpPack>::iterator it = nodes[j]->begin();
        // 首先判断it的操作类型
        if (it->op) //是除法
        {
            // 判定是否只有除法
            if (only_div[j]) // 只有一个除法
            {
                // 需要3001读入一个reg，然后再读入rt进行除法，需要两个slot：i i+1
                // 检查rt是否valid
                if (!EleNodePointer[it->rt]->getValid())
                    continue;
                // 判定操作数是否ready
                if ((EleNodePointer[it->rt]->getTime() > (i + 1)) || (EleNodePointer[it->rd]->getTime() > i))
                    continue;
                // 检查rd能否放入i
                int ok1 = check(it->rd, ocp_rd[i]);
                if (!ok1) continue;
                // 检查rt能否放入i+1
                int ok2 = check(it->rt, ocp_rd[i + 1]);
                if (!ok2) continue;
                
                //被除数从regF中来，所以肯定是20
                int ok3 = check(it->rd, ocp_wr[i + 1 + LAT_1]);
                if (!ok3) continue;

                // 满足条件！ 将该操作调度到i和i+1的PE j上
                inst[i][j].rs = it->rd;
                inst[i][j].op = 21;

                inst[i + 1][j].rs = it->rd; //增加
                inst[i + 1][j].rt = it->rt;
                inst[i + 1][j].op = 20;
                
                // 处理该操作带来的后果
                //ok_to_wb[j] = 1; // 标志5拍之后可以进行写回
                //ok_to_wb_time[j] = i + 5;
                
                if (ok1 == 1) ocp_rd[i]->push_back(it->rd);
                if (ok2 == 1) ocp_rd[i + 1]->push_back(it->rt);
                ocp_wr[i + 1 + LAT_1]->push_back(it->rd);
                EleNodePointer[it->rd]->setTime(i + 1 + LAT_1 + 1);
                EleNodePointer[it->rd]->setValid(1);
                (*p_current)--;

                nodes[j]->erase(it); // 在nodes中删除该操作
                            
            }
            else // 不止有一个除法，所以不用读入reg，因为被除数要么从sub-result来，要么sub-result的结果已经存到了regF中    
            {
                // 检查rt是否valid
                if (!EleNodePointer[it->rt]->getValid())
                    continue;
                //判定操作数（除数）是否ready
                if (EleNodePointer[it->rt]->getTime() > i)
                    continue;
                // 检查rt能否放入i
                int ok1 = check(it->rt, ocp_rd[i]);
                if (!ok1) continue;
                int ok2 = check(it->rd, ocp_wr[i + LAT_1]);
                if (!ok2) continue;
                // 满足条件！ 将该操作调度到i的PE j上
                inst[i][j].rs = it->rd; //增加
                inst[i][j].rt = it->rt;
                if(inst[i - 1][j].op == 17 || inst[i - 1][j].op == 18) //sub之后紧接div
                    inst[i][j].op = 19;
                else
                    inst[i][j].op = 20;
                
                // 处理该操作带来的后果
                //ok_to_wb[j] = 1; // 标志4拍之后可以进行写回
                //ok_to_wb_time[j] = i + 4;

                if (ok1 == 1) ocp_rd[i]->push_back(it->rt);
                ocp_wr[i + LAT_1]->push_back(it->rd);
                EleNodePointer[it->rd]->setTime(i + LAT_1 + 1);
                EleNodePointer[it->rd]->setValid(1);
                (*p_current)--;

                nodes[j]->erase(it); // 在nodes中删除该操作
            }
        }
        else // 是ms
        {
            // 判定AB冲突情况
            if (it->rs % NBANK == it->rt % NBANK) // AB冲突，需要两个slot：i,i+1
            {
                // 检查rs, rt是否valid
                if (!(EleNodePointer[it->rt]->getValid() && EleNodePointer[it->rs]->getValid()))
                    continue;
                // 判定regC是否ready
                if (regC_ready_time[j] > (i + 1)) //受到mac操作影响，regC/mac_result还不能读。
                    continue;
                // 判定操作数是否ready
                if ((EleNodePointer[it->rs]->getTime() > (i + 1)) || (EleNodePointer[it->rt]->getTime() > i))
                    continue;
                // 检查rt能否放入i
                int ok1 = check(it->rt, ocp_rd[i]);
                if (!ok1) continue;
                // 检查rs能否放入i+1
                int ok2 = check(it->rs, ocp_rd[i + 1]);
                if (!ok2) continue;
                //满足条件！将该操作调度到i和i+1的PE j上
                inst[i][j].rt = it->rt;
                inst[i][j].op = 13;

                inst[i + 1][j].op = 14;
                inst[i + 1][j].rs = it->rs;
                
                // 处理该操作带来的后果
                regC_ready_time[j] = i + 1 + 3;
                if ((nodes[j]->size() == 1) || (nodes[j]->size() == 2 && (it + 1)->op)) //这个m就是最后一次操作了，之后就s
                    ok_to_sub[j] = 1; // 可以减法

                if (ok1 == 1) ocp_rd[i]->push_back(it->rt);
                if (ok2 == 1) ocp_rd[i + 1]->push_back(it->rs);
                nodes[j]->erase(it); // 在nodes中删除该操作
            }
            else // AB未冲突，需要考虑上一个操作是否连续的情况
            {
                // 检查rs, rt是否valid
                if (!(EleNodePointer[it->rt]->getValid() && EleNodePointer[it->rs]->getValid()))
                    continue;
                // 判定regC是否ready
                if (regC_ready_time[j] > i) //受到mac操作影响，regC/mac_result还不能读。
                    continue;
                // 判定操作数是否ready
                if ((EleNodePointer[it->rs]->getTime() > i) || (EleNodePointer[it->rt]->getTime() > i))
                    continue;
                // 检查rt能否放入i
                int ok1 = check(it->rt, ocp_rd[i]);
                if (!ok1) continue;
                // 检查rs能否放入i
                int ok2 = check(it->rs, ocp_rd[i]);
                if (!ok2) continue;
                //满足条件！将该操作调度到i的PE j上
                inst[i][j].rs = it->rs;
                inst[i][j].rt = it->rt;
                if (regC_ready_time[j] == i) //数据直连mac_result
                    inst[i][j].op = 15;
                else //数据从regC来
                    inst[i][j].op = 12;
                
                // 处理该操作带来的后果
                regC_ready_time[j] = i + 3;
                if ((nodes[j]->size() == 1) || (nodes[j]->size() == 2 && (it + 1)->op)) //这个m就是最后一次操作了，之后就s
                    ok_to_sub[j] = 1; // 可以减法

                if (ok1 == 1) ocp_rd[i]->push_back(it->rt);
                if (ok2 == 1) ocp_rd[i]->push_back(it->rs);
                nodes[j]->erase(it); // 在nodes中删除该操作
            }
        }
    }
}

int simulate(InstPack** inst, std::vector<float>& Ax, int time, const int n_node) {
    std::vector<float> regC(n_node, 0);
    std::vector<float> reg(n_node);
    std::vector<int> ele(n_node); //每次减法或者读入regF的时候，记录

    for (int i = 0; i < time; i++) {
        std::cout << "Ax[40641] = " << Ax[40641] << std::endl;

        for (int j = 0; j < NPE; j++) {
            if (inst[i][j].op == 0 || inst[i][j].op == 2 || inst[i][j].op == 5 || inst[i][j].op == 7 || inst[i][j].op == 9 || inst[i][j].op == 10 || inst[i][j].op == 13)
                continue;
            else if (inst[i][j].op == 1)
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
            else if (inst[i][j].op == 3)
            {
                float A = Ax[inst[i][j].rs];
                float B = Ax[inst[i - 1][j].rt];
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
            else if (inst[i][j].op == 4 || inst[i][j].op == 6 || inst[i][j].op == 8 || inst[i][j].op == 11)
            {
                float A, B, C;
                if (inst[i][j].op == 4) 
                {
                    A = Ax[inst[i][j].rs];
                    B = Ax[inst[i][j].rt];
                }
                else if (inst[i][j].op == 6)
                {
                    A = Ax[inst[i][j].rs];
                    B = Ax[inst[i - 1][j].rt];
                }
                else if (inst[i][j].op == 8)
                {
                    A = Ax[inst[i - 1][j].rs];
                    B = Ax[inst[i - 1][j].rt];
                }
                else
                {
                    A = Ax[inst[i - 1][j].rs];
                    B = Ax[inst[i - 2][j].rt];
                }
                C = Ax[inst[i][j].rd];
                Ax[inst[i][j].rd] = C - A * B;
                std::cout << "time: " << i << "\tPE: " << j << "\top: ";
                std::cout << C << " - " << A << " * " << B << " = " << Ax[inst[i][j].rd] << endl; 
            }
            else if (inst[i][j].op == 17 || inst[i][j].op == 18)
            {
                float X;
                float Y;
                Y = regC[j];
                X = Ax[inst[i][j].rs];
                reg[j] = X - Y;
                std::cout << "time: " << i << "\tPE: " << j << "\top: ";
                std::cout << X << " - " << Y << " = " << reg[j] << endl; 
                ele[j] = inst[i][j].rs;
            }
            else if (inst[i][j].op == 22 || inst[i][j].op == 23)
            {
                float X;
                float Y;
                Y = regC[j];
                X = Ax[inst[i][j].rs];
                Ax[inst[i][j].rs] = X - Y;
                std::cout << "time: " << i << "\tPE: " << j << "\top: ";
                std::cout << "Ax[" << inst[i][j].rs << "] = " << X << " - " << Y << " = " << Ax[inst[i][j].rs] << endl; 
            }
            else if (inst[i][j].op == 21)
            {
                reg[j] = Ax[inst[i][j].rs];
                std::cout << "time: " << i << "\tPE: " << j << "\top: ";
                std::cout << "reg[" << j << "] = " << reg[j] << endl; 
                ele[j] = inst[i][j].rs;
            }
            else if (inst[i][j].op == 19 || inst[i][j].op == 20)
            {
                float B = Ax[inst[i][j].rt];
                float A = reg[j];
                if (B == 0)
                {
                    std::cout << "divided by zero in inst[" << i << "][" << j << "]\n";
                    return -1;
                }
                reg[j] = A / B;
                std::cout << "time: " << i << "\tPE: " << j << "\top: ";
                std::cout << "Ax[" << ele[j] << "] = " << A << " / " << B << " = " << reg[j] << endl; 
                Ax[ele[j]] = reg[j];
            }
            else if (inst[i][j].op == 12 || inst[i][j].op == 15)
            {
                float C = regC[j];
                float A = Ax[inst[i][j].rs];
                float B = Ax[inst[i][j].rt];
                regC[j] = C + A * B;
                std::cout << "time: " << i << "\tPE: " << j << "\top: ";
                std::cout << C << " + " << A << " * " << B << " = " << regC[j] << endl; 
            }
            else if (inst[i][j].op == 14)
            {
                float C = regC[j];
                float A = Ax[inst[i][j].rs];
                float B = Ax[inst[i - 1][j].rt];
                regC[j] = C + A * B;
                std::cout << "time: " << i << "\tPE: " << j << "\top: ";
                std::cout << C << " + " << A << " * " << B << " = " << regC[j] << endl;
            }

        }
    }
    return 0;
}

int dfs(EleNode* EleNodePointer[], std::vector<bool>& visited, int root)
{
    if (visited[root]) 
        return EleNodePointer[root]->getPri();
    std::vector<int> childVec = EleNodePointer[root]->getChild();
    // 此前没有被访问过
    if (childVec.size() == 0) //说明是叶子节点 
    {
        EleNodePointer[root]->setPri(0);
        visited[root] = 1;
        return 0;
    }
    else //说明该节点有子节点，需要遍历各个子节点
    {
        unsigned max = 0;
        for (int j : childVec)
        {
            unsigned temp = dfs(EleNodePointer, visited, j);
            if (temp > max)
                max = temp;
        }
        EleNodePointer[root]->setPri(max + 1);
        visited[root] = 1;
        return (max + 1);
    }
}

void initAddPri(EleNode* EleNodePointer[], int nnz) 
{
    std::vector<bool> visited(nnz, 0);
    // 对graph进行深度优先搜索。
    for (int i = 0; i < nnz; i++)
    {
        if (visited[i]) continue; //被访问过
        dfs(EleNodePointer, visited, i);
    }
}

void sortOkToDo(EleNode* EleNodePointer[], std::vector<OpPack>& pool)
{
    std::vector<unsigned> pri(pool.size());
    std::vector<int> pri2(pool.size());
    std::vector<size_t> pri3(pool.size());
    for (size_t i = 0; i < pool.size(); i++)
    {
        pri[i] = EleNodePointer[pool[i].rd]->getPri();
        pri2[i] = EleNodePointer[pool[i].rd]->getToDo();
        pri3[i] = (EleNodePointer[pool[i].rd]->getChild()).size();
    }

    // 创建索引向量 indices
    std::vector<size_t> indices(pool.size());
    std::iota(indices.begin(), indices.end(), 0);

    // 根据 pri、pri2 和 pri3 从大到小排序 indices
    std::sort(indices.begin(), indices.end(), [&](size_t a, size_t b) {
        if (pri3[a] == pri3[b]) {
            if (pri2[a] == pri2[b]) {
                return pri[a] > pri[b];
            } else {
                return pri2[a] > pri2[b];
            }
        } else {
            return pri3[a] > pri3[b];
        }
    });

    // 使用排序后的 indices 更新原始的 pool
    std::vector<OpPack> sortedPool(pool.size());
    for (size_t i = 0; i < pool.size(); ++i) {
        sortedPool[i] = pool[indices[i]];
    }

    pool = sortedPool;
}



int getLat(InstPack** inst, int t, int time) {
    for (int i = t; i >= time; i--) {
        for (int j = 0; j < NPE; j++) {
            if (inst[i][j].op != 0)
                return i;
        } 
    }
    return 0;
}

std::string intToBinaryString16Bit(int r) {
    // 使用bitset来获取二进制表示
    std::bitset<16> binaryRepresentation(r);

    // 将bitset转换为字符串
    std::string binaryString = binaryRepresentation.to_string();

    return binaryString;
}

std::string intToBinaryString5bit(int num) {
    if (num < 0 || num > 31) {
        return "Invalid input";
    }
    return std::bitset<5>(num).to_string();
}


void writeInst(InstPack** inst, const int time, const std::string& f1, const std::string& f2, const std::string& f3, const std::string& f4, const std::string& f5, const std::string& f6) {
    std::ofstream file1(f1);
    std::ofstream file2(f2);
    std::ofstream file3(f3);
    std::ofstream file4(f4);
    std::ofstream file5(f5);
    std::ofstream file6(f6);
    if (!file1.is_open()) {
        std::cerr << "Error: Unable to open file " << f1 << std::endl;
        return;
    }

    if (!file2.is_open()) {
        std::cerr << "Error: Unable to open file " << f2 << std::endl;
        return;
    }

    if (!file3.is_open()) {
        std::cerr << "Error: Unable to open file " << f3 << std::endl;
        return;
    }

    if (!file4.is_open()) {
        std::cerr << "Error: Unable to open file " << f4 << std::endl;
        return;
    }

    if (!file5.is_open()) {
        std::cerr << "Error: Unable to open file " << f5 << std::endl;
        return;
    }

    if (!file6.is_open()) {
        std::cerr << "Error: Unable to open file " << f6 << std::endl;
        return;
    }
// generate wea.txt
    for (int i = 0; i < time; i++) {
        std::vector<std::string> strings(NBANK);
        for (int j = NBANK - 1; j >= 0; j--) {
            strings[j] = "0";
        }
        
        for(int j = NPE; j >= 0; j--) {
            int des_bank = -1;
            if (inst[i][j].op == 1 || inst[i][j].op == 3 || inst[i][j].op == 19 || inst[i][j].op == 20 || inst[i][j].op == 22 || inst[i][j].op == 23)
                des_bank = inst[i][j].rs % NBANK;
            else if (inst[i][j].op == 4 || inst[i][j].op == 6 || inst[i][j].op == 8 || inst[i][j].op == 11)
                des_bank = inst[i][j].rd % NBANK;
            
            if (des_bank != -1)            
                strings[des_bank] = "1";
        }

        std::string bs1;
        for (int j = NBANK - 1; j >= 0; j--)
        {
            bs1 += strings[j];
            if (j % 4 == 0 && j != 0)
                bs1 += "_";
        }

        file1 << bs1 << std::endl;
    }

// generate addr.txt
    for (int i = 0; i < time; i++) {
        std::vector<std::string> strings(NBANK);
        for (int j = NBANK - 1; j >= 0; j--) {
            strings[j] = "11111111111";
        }
        for (int j = NPE - 1; j >= 0; j--) {
            if (inst[i][j].op == 0) continue;
            int rs = inst[i][j].rs;
            int rt = inst[i][j].rt;
            int rd = inst[i][j].rd;
            
            if (rs != -1 && (inst[i][j].op != 19) && (inst[i][j].op != 20))
            {
                int rs_addr = rs / NBANK;
                int rs_bank = rs % NBANK;
                strings[rs_bank] = std::bitset<11>(rs_addr).to_string();
            }
            if (rt != -1)
            {
                int rt_addr = rt / NBANK;
                int rt_bank = rt % NBANK;
                strings[rt_bank] = std::bitset<11>(rt_addr).to_string();
            }
            if (rd != -1)
            {
                int rd_addr = rd / NBANK;
                int rd_bank = rd % NBANK;
                strings[rd_bank] = std::bitset<11>(rd_addr).to_string();
            }
        }
        std::string bs2;
        for (int j = NBANK - 1; j >= 0; j--)
        {
            bs2 += strings[j];
            if (j != 0)
                bs2 += "_";
        }

        file2 << bs2 << std::endl;
    }

//generate sel2.txt
    for (int i = 0; i < time; i++) {
        std::vector<std::string> strings(NBANK);
        for (int j = 0; j < NBANK; j++) {
            strings[j] = std::bitset<4>(j / 2).to_string();
        }

        for (int j = 0; j < NPE; j++) {
            if (inst[i][j].op == 0 || inst[i][j].op == 2 || inst[i][j].op == 5 || inst[i][j].op == 7 || inst[i][j].op == 9 || inst[i][j].op == 10
                || inst[i][j].op == 12 || inst[i][j].op == 13 || inst[i][j].op == 14 || inst[i][j].op == 15 
                || inst[i][j].op == 17 || inst[i][j].op == 18 || inst[i][j].op == 21) continue; // 没有写回操作
            else if (inst[i][j].op == 1 || inst[i][j].op == 3 || inst[i][j].op == 19 || inst[i][j].op == 20 || inst[i][j].op == 22 || inst[i][j].op == 23)
                strings[inst[i][j].rs % NBANK] = std::bitset<4>(j).to_string();
            else if (inst[i][j].op == 4 || inst[i][j].op == 6 || inst[i][j].op == 8 || inst[i][j].op == 11)
                strings[inst[i][j].rd % NBANK] = std::bitset<4>(j).to_string();
        }
        std::string bs3;
        for (int j = NBANK - 1; j >= 0; j--)
        {
            bs3 += strings[j];
            if (j != 0)
            bs3 += "_";
        }
        file3 << bs3 << std::endl;
    }

// generate sel1.txt
    for (int i = 0; i < time; i++)
    {
        std::vector<std::string> strings(3 * NPE);
        for (int j = 0; j < NBANK; j++) {
            strings[j] = intToBinaryString5bit(j);
        }
        for (int j = NBANK; j < 3 * NPE; j++) {
            strings[j] = intToBinaryString5bit(j - NBANK);
        }

        // 先读取时间i的所有指令，j负责遍历所有pe的inst
        for (int j = 0; j < NPE; j++)
        {
            if (inst[i][j].op == 0) continue;
            int rs = inst[i][j].rs;
            int rt = inst[i][j].rt;
            int rd = inst[i][j].rd;
            // 排列顺序（rs,rt,rd)
            if (rs != -1 && inst[i][j].op != 19 && inst[i][j].op != 20)
            {
                strings[3 * j + 2] = std::bitset<5>(rs % NBANK).to_string();
            }

            if (rt != -1)
            {
                strings[3 * j + 1] = std::bitset<5>(rt % NBANK).to_string();
            }

            if (rd != -1)
            {
                strings[3 * j] = std::bitset<5>(rd % NBANK).to_string();
            }
        }
        
        std::string bs4;
        for (int j = 3 * NPE - 1; j >= 0; j--)
        {
            bs4 += strings[j];
            if (j != 0)
            bs4 += "_";
        }
        file4 << bs4 << std::endl;
    }

// generate op.txt
    for (int i = 0; i < time; i++) {
        for (int j = NPE - 1; j >= 0; j--) {
            std::string bs5 = intToBinaryString5bit(inst[i][j].op);
            file5 << bs5;
            if (j != 0) file5 << "_";
        }
        file5 << std::endl;
    }

    file6 << std::bitset<16>(time).to_string() << std::endl;

    file1.close();file2.close();file3.close();file4.close();file5.close();file6.close();
}

void writeData(const std::vector<float>& Ax, const int nnz, const std::string& filename) {
    std::ofstream file(filename);
    
    if (!file.is_open()) {
        std::cerr << "Error: Unable to open file " << filename << std::endl;
        return;
    }
    // 补齐不足16个的0
    int complete = NBANK - (nnz % NBANK);
    if (complete == NBANK)
    {
        std::bitset<32> binaryRepresentation(nnz / NBANK);
        file << std::hex << std::setfill('0') << std::setw(8) << binaryRepresentation.to_ulong() << std::endl;

    }
    else
    {
        std::bitset<32> binaryRepresentation((nnz / NBANK) + 1);
        file << std::hex << std::setfill('0') << std::setw(8) << binaryRepresentation.to_ulong() << std::endl;

    }

    // 将浮点数转换为十六进制字符串并以8个字符的宽度输出到文件
    for (float value : Ax) {
        unsigned int intValue;

        std::memcpy(&intValue, &value, sizeof(value));

        // Convert to binary representation with leading zeros
        std::bitset<32> binaryRepresentation(intValue);

        // Output the binary representation as hex with leading zeros
        file << std::hex << std::setfill('0') << std::setw(8) << binaryRepresentation.to_ulong() << std::endl;
    }

    if (complete != 16) //需要对应个数
    {
        for (int i = 0; i < complete; i++)
        {
            file << "00000000" << std::endl;
        }
    }

    file.close();
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
