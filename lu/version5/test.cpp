#include "mymethod.h"

int main(int argc, char* argv[]) {
    if (argc != 4) {
        std::cerr << "Usage: " << argv[0] << " <matrix_file.mtx> <fill_matrix.mtx> <out_result_matrix.mtx>" << std::endl;
        return 1;
    }

    const char* filename = argv[1];
    const char* fillmtx = argv[2];
    const char* result = argv[3];
    const char* inst_file = "inst.txt";
    const char* data_file = "data.txt";

    vector<int> CAi, CAp;
    vector<float> CAx;
    int n;
    long int nnz;

    readMatrixMarket(filename, CAx, CAi, CAp, &n, &nnz);
    cout << "n: " << n << endl;
    cout << "nnz: " << nnz << endl;

    //fill in for CSC format
    vector<int> CAi_fill, CAp_fill, CAd_fill;
    vector<float> CAx_fill;
    int fill_ok = fillIn(CAx, CAi, CAp, n, CAx_fill, CAi_fill, CAp_fill, CAd_fill);   
    if (fill_ok != 0) cout << "ERROR: Fill in failed!" << endl;
    cout <<"CSC format: after fill in" << endl; 
    printSparse(CAx_fill, CAi_fill, CAp_fill);
    std::cout << "CAd_fill: ";
    for (int val : CAd_fill) 
    {
        std::cout << val << " ";
    }
    std::cout << "\n";

    int nnz_fill = CAi_fill.size();


    //输出填充后的文件，方便matlab观察以及得到lu分解正确结果
    writeCSCtoMTX(CAx_fill, CAi_fill, CAp_fill, n, n, nnz_fill, fillmtx);

    //flops计数
    int div_count = divCount(CAp_fill, CAd_fill, n);
    cout << "div count is " << div_count << endl;

    int ms_count = msCount(CAi_fill, CAp_fill, CAd_fill, n);
    cout << "ms count is " << ms_count << endl;

    cout << "div + ms count is " << div_count + ms_count << " the ideal cycle is " << (div_count + ms_count)/NPE  + 1<< endl;
    cout << "flops: " << 2 * ms_count + div_count << endl;


    EleNode* EleNodePointer[nnz_fill];  //创建一个EleNode指针数组
 //   InstPack inst[20000][NPE];  //共INSTNUM条指令，每条指令包含NPE组信息
    int sch2 = 0; //没有开启第二种调度
    std::vector<int> remain_node;
    //基于元素分析
    int build_ok = buildGraph(EleNodePointer, n, CAi_fill, CAp_fill, CAd_fill, remain_node);
    if (build_ok != 0) cout << "ERROR: Build Graph failed!" << endl;
    else cout << "SUCCESS: Build Graph!" << endl; 

    std::vector<OpPack> wl;
    std::vector<OpPack> ok_to_do;
    std::vector<int> newly_valid;
    int time = 0;
    //观察一开始就ready的节点，检查其子节点的操作是否可以进行
    int initial_ok = initialWl(EleNodePointer, nnz_fill, wl);

    //打印检查wl
    if (initial_ok != 1) cout << "ERROR: Initialize waiting list failed!" << endl;
    else cout << "SUCCESS: Initialize waiting list!" << endl;
    

    //从wl取操作到ok_to_do，原则是新加入的操作写回地址不能与原有操作的写回地址重合（完全一致）
    addOkToDo(wl, ok_to_do);
    std::cout << "SUCCESS: add ok to do list at time " << time << endl;

    // 释放分配的内存
 //   for (int i = 0; i < INSTNUM; ++i) {
  //      delete ocp[i];
  //  }

    // 释放动态分配的内存
    for (int i = 0; i < nnz_fill; i++) {
        delete EleNodePointer[i];
    }



    return 0;
}
