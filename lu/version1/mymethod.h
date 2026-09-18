#include <iostream>
#include <fstream>
#include <vector>
#include <sstream>
#include <algorithm>

using namespace std;
//small case
/*
#define INSTNUM 100
#define NPE 4
#define NBANK 8
#define DELAY 5 //同一个数两次操作周期间隔5
*/
//large case

#define INSTNUM 20000
#define NPE 16
#define NBANK 32
#define DELAY 5

typedef struct {
    int rs = -1;
    int rt = -1;
    int c = -1;
    int op = -1; //0代表ms，1代表div
 //   bool last = -1; //1代表是最后一个操作
} OpPack;

class EleNode {
public:
    std::vector<OpPack> pool;

    EleNode(int nValue) : n(nValue) {}

    int getN() {
        return n;
    }

    void setAi(int aiValue) {
        ai = aiValue;
    }

    int getAi() {
        return ai;
    }

    void setTime(int i) {
        ready_time = i;
    }

    int getTime() {
        return ready_time;
    }

    void setValid(bool i) {
        valid = i;
    }

    bool getValid() {
        return valid;
    }

    void setToDo(int i) {
        to_do = i;
    }

    int getToDo() {
        return to_do;
    }

    void addChild(int n) {
        child.push_back(n);
    }

    const std::vector<int>& getChild() const {
        return child;
    }

    // 打印child向量元素
    void printChild() {
        for (const auto& element : child) {
            std::cout << element << " ";
        }
        std::cout << std::endl;
    }

    // 打印pool向量元素
    void printPool() {
        for (const auto& element : pool) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.c << "," << element.op << "> ";
        }
        std::cout << std::endl;
    }


private:
    int n;  
    int ai; //该元素地址序号，简单数据映射下ai=数组偏移量n
    //int bank; //n % NBANK
    //int addr; //n / NBANK
    int ready_time = 0; //每次作为rs被读出操作的时候会被更新
    int valid = 0; //to_do变为0时则为valid
    int to_do = -1; //还要做多少次计算写回操作，如果为0则说明该值在ready_time之后完全算好
    std::vector<int> child; //它指向的子节点偏移量n'
    //当一个数valid后，开始检查它指向的所有子节点。遍历检查pair中有误涉及到的更新。若有，将pair提取到ok_to_do池子中。
};

class ColNode {
public:
    ColNode(int colValue) : col(colValue) {}

    void addChild(int n) {
        children.push_back(n);
    }

    int getChildSize() {
        return children.size();
    }

    void addDpd(int n){
        dpd.push_back(n);
    }

    int getDpdSize(){
        return dpd.size();
    }

    void setCol(int colValue) {
        col = colValue;
    }

    int getCol() {
        return col;
    }

    void setLevel(int l){
        level = l;
    }

    int getLevel(){
        return level;
    }

    void setNeedDiv(int i){
        need_div = i;
    }

    int getNeedDiv(){
        return need_div;
    }

    void setReady(int i){
        ready_time = i;
    }

    int getReady(){
        return ready_time;
    }

    const std::vector<int>& getDpd() const {
        return dpd;
    }

    const std::vector<int>& getChildren() const {
        return children;
    }

private:
    int col;
    int level = 1;
    int need_div = 0;
    int ready_time = 0;
    std::vector<int> children; //依赖于它的右列
    std::vector<int> dpd; //depend table它依赖的左列
};

// 定义一个结构体用于保存原始位置和值
struct Pair {
    int index;
    int value;
};

typedef struct {
    int rs = -1; //*rs = A
    int rt = -1; //*rt = B
    int op = -1;
    int sel1 = -1; //sel1 = 0代表此时未输入rt，仅输入rs，所以rt保持不变；sel1 = 1代表此时仅输入rt，因此rt要变。
    int sel2 = -1;
    bool valid = 0;
    //op = 0: A * B
    //op = 1: A / B
    //op = 2: C - R
    //op = 3: A / B
    // op = 1,2,3时的rs是写回地址，在时刻1读出rs后，在时刻5写回rs，在时刻6才能再次读出 
} InstPack;


bool comparePairs(const Pair& a, const Pair& b);

void readMatrixMarket(const char* filename, vector<float>& CAx, vector<int>& CAi, vector<int>& CAp, int* p_n, long int* p_nnz);

void cscToCsr(
    const std::vector<float>& CAx, // CSC存储的矩阵非零元素
    const std::vector<int>& CAi, // CSC存储的行索引
    const std::vector<int>& CAp, // CSC存储的列指针
    std::vector<float>& RAx,       // 转换后的CSR存储的矩阵非零元素
    std::vector<int>& RAi,       // 转换后的CSR存储的列索引
    std::vector<int>& RAp        // 转换后的CSR存储的行指针
);

void printSparse(
    const std::vector<float>& Ax, // 非零元素
    const std::vector<int>& Ai, // 索引
    const std::vector<int>& Ap // 指针
);

std::vector<int> extractSubVectorInt(const std::vector<int>& original, int start, int end);

std::vector<float> extractSubVectorFloat(const std::vector<float>& original, int start, int end);

void addMissingElements(const std::vector<int>& Ai, int start, int end, std::vector<int>& subAi, std::vector<float>& subAx, std::vector<int>& myQue);

void addMissingElementsFalse(const std::vector<int>& Ai, int start, int end, std::vector<int>& subAi, std::vector<float>& subAx, std::vector<int>& myQue);

int findRowPosition(const std::vector<int>& Ai_new, int row);

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
);

int dpdDetect(ColNode* root, ColNode* ColNodePointer[], int n, const std::vector<int>& Ai, const std::vector<int>& Ap, const std::vector<int>& Ad);

void writeCSCtoMTX(const std::vector<float>& Ax, const std::vector<int>& Ai, const std::vector<int>& Ap, const int numRows, const int numCols, const int numNonZero, const std::string& filename);

long int divCount(const std::vector<int>& Ap, const std::vector<int>& Ad, const int n);

long int msCount(const std::vector<int>& Ai, const std::vector<int>& Ap, const std::vector<int>& Ad, const int n);

int check0(const int rs, const int rt, InstPack* inst_i);

void addToSpot(InstPack* inst_i, const int rs, const int rt);

void freshBottom(int* bottom, const std::vector<int>& full);

int findRtSopt(int rs, int rt, int* p_bottom, InstPack inst[][NPE], std::vector<int>& full, int* p_max_ready);

void printInst(const InstPack inst[][NPE], const int start, const int end);

void searchLevelCol(ColNode* ColNodePointer[], const int n, const int level, std::vector<int>& col);

bool compareByLevel(ColNode* a, ColNode* b);

void recordNewPos(ColNode* ColNodePointer[], const int n, std::vector<int>& pos);

int addDivCol(ColNode* ColNodePointer[], const int n,
    const int level, int* p_start_pos, std::vector<int>& ok_to_div_pool);

int addMsCol(ColNode* ColNodePointer[], const int n,
    const int level, int* p_start_pos, std::vector<int>& ok_to_ms_pool);

//void vDel(std::vector<int>& v, int target);

int searchElement(const std::vector<int>& vec, int start, int end, int row, int* p_location);

int buildGraph(EleNode* EleNodePointer[], int nnz, const std::vector<int>& Ai, const std::vector<int>& Ap, const std::vector<int>& Ad);

int initialWl(EleNode* EleNodePointer[], int nnz, std::vector<OpPack>& wl);

int findC(const std::vector<OpPack>& pool, int c);

void addOkToDo(std::vector<OpPack>& wl, std::vector<OpPack>& pool, int time);

int check(int value, std::vector<int>* vec);

void schedule(InstPack inst[][NPE], std::vector<int>* ocp[], EleNode* EleNodePointer[], std::vector<OpPack>& pool, int i, std::vector<int>& newly_valid);

void printInst(const InstPack inst[][NPE], const int start, const int end);

void addWl(EleNode* EleNodePointer[], std::vector<int>& newly_valid, std::vector<OpPack>& wl);

int simulate(const InstPack inst[][NPE], std::vector<float>& Ax, const std::vector<int>& Ai, int time);

void compareGolden(const std::vector<float>& g, const std::vector<float>& my, const int nnz);