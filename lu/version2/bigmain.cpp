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
    InstPack inst[INSTNUM][NPE];  //共INSTNUM条指令，每条指令包含NPE组信息
    cout << "SUCCESS: 初始化inst!" << endl;
    std::vector<int>* ocp[INSTNUM];  //一个长度为INSTNUM的数组，每个元素是一个向量的指针
    // 为每个数组元素分配一个向量
    for (int i = 0; i < INSTNUM; ++i) {
        ocp[i] = new std::vector<int>;
    }
    cout << "SUCCESS: 分配ocp!" << endl;


    //基于元素分析
    int build_ok = buildGraph(EleNodePointer, n, CAi_fill, CAp_fill, CAd_fill);
    if (build_ok != 0) cout << "ERROR: Build Graph failed!" << endl;
    else cout << "SUCCESS: Build Graph!" << endl;

    //打印
    /*
    for (int i = 0; i < nnz_fill; i++) {
        std::cout << "\nNode " << i << " - n: " << EleNodePointer[i]->getN() << ", ai: " << EleNodePointer[i]->getAi() << std::endl;
        std::cout << "ready time: " << EleNodePointer[i]->getTime() << ", valid: " << EleNodePointer[i]->getValid() << std::endl;
        std::cout << "child: ";
        EleNodePointer[i]->printChild();
        std::cout << "pool: ";
        EleNodePointer[i]->printPool();
        std::cout << "to_do: " << EleNodePointer[i]->getToDo() << std::endl;
    }
    std::cout << std::endl;
*/

    std::vector<OpPack> wl;
    std::vector<OpPack> ok_to_do;
    std::vector<int> newly_valid;
    int time = 0;
    //观察一开始就ready的节点，检查其子节点的操作是否可以进行
    int initial_ok = initialWl(EleNodePointer, nnz_fill, wl);

    //打印检查wl
    if (initial_ok != 1) cout << "ERROR: Initialize waiting list failed!" << endl;
    else cout << "SUCCESS: Initialize waiting list!" << endl;
/*    std::cout << "waiting list is: " << endl;
    for (const auto& element : wl) {
        std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
    }
*/


    //从wl取操作到ok_to_do，原则是新加入的操作写回地址不能与原有操作的写回地址重合（完全一致）
    addOkToDo(wl, ok_to_do);
    std::cout << "SUCCESS: add ok to do list at time " << time << endl;
/*    std::cout << "ok to do list is: " << endl;
    for (const OpPack& element : ok_to_do) {
        std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
    }
    std::cout << "waiting list is: " << endl;
    for (const OpPack& element : wl) {
        std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
    }
*/

    //将ok_to_do里面的内容尽可能调度到#0上面
    schedule(inst, ocp, EleNodePointer, ok_to_do, time, newly_valid);
    std::cout << "SUCCESS: schedule at time" << time << endl;
/*
    std::cout << "ok to do list is: " << endl;
    for (const OpPack& element : ok_to_do) {
        std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
    }
*/
    //打印
/*    for (int i = 0; i < nnz_fill; i++) {
        std::cout << "\nNode " << i << " - n: " << EleNodePointer[i]->getN() << ", ai: " << EleNodePointer[i]->getAi() << std::endl;
        std::cout << "ready time: " << EleNodePointer[i]->getTime() << ", valid: " << EleNodePointer[i]->getValid() << std::endl;
        std::cout << "child: ";
        EleNodePointer[i]->printChild();
        std::cout << "pool: ";
        EleNodePointer[i]->printPool();
        std::cout << "to_do: " << EleNodePointer[i]->getToDo() << std::endl;
    }
    std::cout << std::endl;

    std::cout << "newly_valid list is: " << endl;
    for (const int& element : newly_valid) {
        std::cout << element << " ";
    }
    std::cout << endl;
*/
    //将newly_valid对应的子节点逐个检查是否可以加入wl
    addWl(EleNodePointer, newly_valid, wl);
    std::cout << "SUCCESS: add waiting list" << endl;
    //打印检查waiting list
/*    std::cout << "ok to do list is: " << endl;
    for (const OpPack& element : ok_to_do) {
        std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
    }
    std::cout << "waiting list is: " << endl;
    for (const OpPack& element : wl) {
        std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
    }
*/

    for (time = 1; time < INSTNUM; time++) {
        //从wl取操作到ok_to_do，原则是新加入的操作写回地址不能与原有操作的写回地址重合（完全一致）
        addOkToDo(wl, ok_to_do);
        std::cout << "SUCCESS: add ok to do list at time " << time << endl;
/*      std::cout << "ok to do list is: " << endl;
        for (const OpPack& element : ok_to_do) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
        }
        std::cout << "waiting list is: " << endl;
        for (const OpPack& element : wl) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
        }
*/
        vector <int>().swap(newly_valid);  //清除容器并最小化它的容量
        schedule(inst, ocp, EleNodePointer, ok_to_do, time, newly_valid);
        std::cout << "SUCCESS: schedule at time " << time << endl;


/*        std::cout << "ok to do list is: " << endl;
        for (const OpPack& element : ok_to_do) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
        }
*/
    //打印
/*      for (int i = 0; i < nnz_fill; i++) {
            std::cout << "\nNode " << i << " - n: " << EleNodePointer[i]->getN() << ", ai: " << EleNodePointer[i]->getAi() << std::endl;
            std::cout << "ready time: " << EleNodePointer[i]->getTime() << ", valid: " << EleNodePointer[i]->getValid() << std::endl;
            std::cout << "child: ";
            EleNodePointer[i]->printChild();
            std::cout << "pool: ";
            EleNodePointer[i]->printPool();
            std::cout << "to_do: " << EleNodePointer[i]->getToDo() << std::endl;
            std::cout << std::endl;
        }
*/
        std::cout << "newly_valid list is: " << endl;
/*        for (const int& element : newly_valid) {
            std::cout << element << " ";
        }
        std::cout << endl;
*/
        //将newly_valid对应的子节点逐个检查是否可以加入wl
        addWl(EleNodePointer, newly_valid, wl);
        std::cout << "SUCCESS: add waiting list" << endl;
        //打印检查waiting list
/*        std::cout << "waiting list is: " << endl;
        for (const OpPack& element : wl) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
        }

        std::cout << "\n\n";
*/
        if ((!wl.size()) && (!ok_to_do.size()))
            break;

    }

    std::cout << "Finished: schedule!\n";
    if ((time + 3) >= INSTNUM) {
        std::cout << "ERROR: instruction space is not enough!\n";
        printInst(inst, 0, INSTNUM - 1);

        std::cout << "ok to do list is: " << endl;
        for (const OpPack& element : ok_to_do) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
        }
        std::cout << "waiting list is: " << endl;
        for (const OpPack& element : wl) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
        }
        
        int simulate_ok = simulate(inst, CAx_fill, INSTNUM);
        if (simulate_ok == 0) cout << "SUCCESS: simulation\n";

        cout <<"CSC format: after simulation" << endl; 
        printSparse(CAx_fill, CAi_fill, CAp_fill);

        //输出填充后的文件，方便matlab观察以及得到lu分解正确结果
        writeCSCtoMTX(CAx_fill, CAi_fill, CAp_fill, n, n, nnz_fill, result);

        // 释放分配的内存
        for (int i = 0; i < INSTNUM; ++i) {
            delete ocp[i];
        }

        // 释放动态分配的内存
        for (int i = 0; i < nnz_fill; i++) {
            delete EleNodePointer[i];
        }

        return 1;
    }

    printInst(inst, 0, time + 3);

    //输出指令
    //得到准确的指令周期
    int latency = getLat(inst, time + 3, time) + 1;
    writeInst(inst, latency, inst_file);
    //输出填充后的CAd_Ax_fill文件
    writeData(CAx_fill, nnz_fill, data_file);

    //写一个模拟验证执行的东西，得到最后的结果
    int simulate_ok = simulate(inst, CAx_fill, time + 3);
    if (simulate_ok == 0) cout << "SUCCESS: simulation\n";

    cout <<"CSC format: after simulation" << endl; 
    printSparse(CAx_fill, CAi_fill, CAp_fill);

    //输出填充后的文件，方便matlab观察以及得到lu分解正确结果
    writeCSCtoMTX(CAx_fill, CAi_fill, CAp_fill, n, n, nnz_fill, result);

    // 释放分配的内存
    for (int i = 0; i < INSTNUM; ++i) {
        delete ocp[i];
    }

    // 释放动态分配的内存
    for (int i = 0; i < nnz_fill; i++) {
        delete EleNodePointer[i];
    }

    return 0;
}
