#include "mymethod.h"

int main(int argc, char* argv[]) {
    if (argc != 4) {
        std::cerr << "Usage: " << argv[0] << " <matrix_file.mtx> <fill_matrix.mtx> <out_result_matrix.mtx>" << std::endl;
        return 1;
    }

    const char* filename = argv[1];
    const char* fillmtx = argv[2];
    const char* result = argv[3];
    const char* inst_file1 = "wea.txt";
    const char* inst_file2 = "addr.txt";
    const char* inst_file3 = "sel2.txt";
    const char* inst_file4 = "sel1.txt";
    const char* inst_file5 = "op.txt";
    const char* data_file = "data.txt";
    const char* count_file = "count.txt";

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
    //InstPack inst[INSTNUM][NPE];  //共INSTNUM条指令，每条指令包含NPE组信息
    InstPack** inst = new InstPack*[INSTNUM];
    for (int i = 0; i < INSTNUM; ++i) {
        inst[i] = new InstPack[NPE];
    }
    cout << "SUCCESS: 初始化inst!" << endl;

    //std::vector<int>* ocp[INSTNUM];  //一个长度为INSTNUM的数组，每个元素是一个向量的指针
    // 为每个数组元素分配一个向量
    //for (int i = 0; i < INSTNUM; ++i) {
    //    ocp[i] = new std::vector<int>;
    //}

    std::vector<int>** ocp_rd = new std::vector<int>*[INSTNUM + NEW_NUM];
    std::vector<int>** ocp_wr = new std::vector<int>*[INSTNUM + NEW_NUM];
    //先初始化数组前十个，此后运行的时候，每时刻都先释放当前，然后再new一个新的。
    for (int i = 0; i < NEW_NUM; ++i) {
        ocp_rd[i] = new std::vector<int>();
        ocp_wr[i] = new std::vector<int>();
    }
    cout << "SUCCESS: 分配ocp!" << endl;
//    std::vector<int>** ocp = new std::vector<int>*[INSTNUM];

    // 初始化数组，为每个元素分配一个 std::vector<int>
//    for (int i = 0; i < INSTNUM; ++i) {
//        ocp[i] = new std::vector<int>();
//    }
    cout << "SUCCESS: 分配ocp!" << endl;

    int sch2 = 0; //没有开启第二种调度
    std::vector<int> remain_node;

    //基于元素分析
    int build_ok = buildGraph(EleNodePointer, n, CAi_fill, CAp_fill, CAd_fill, remain_node);
    if (build_ok != 0) cout << "ERROR: Build Graph failed!" << endl;
    else cout << "SUCCESS: Build Graph!" << endl;

    initAddPri(EleNodePointer, nnz_fill);
    /*
    for (int val : remain_node) 
    {
        std::cout << val << " ";
    }
    std::cout << "\n";
    std::cout << "the size of remain_node is " << n_node << std::endl;
    */

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
        std::cout << "pri: " << EleNodePointer[i]->getPri() << std::endl;
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
        std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "> " << endl;;
    }*/
/*
    std::cout << "waiting list is: " << endl;
    for (const OpPack& element : wl) {
        std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
    }
*/

    sortOkToDo(EleNodePointer, ok_to_do);
/*    std::cout << "after sort: ok to do list is: " << endl;
    for (const OpPack& element : ok_to_do) {
        std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "> " << endl;;
    }
*/
    //将ok_to_do里面的内容尽可能调度到#0上面
    schedule(inst, ocp_rd, ocp_wr, EleNodePointer, ok_to_do, time, newly_valid, remain_node);
    std::cout << "SUCCESS: schedule at time" << time << endl;
/*
    for (int val : remain_node) 
    {
        std::cout << val << " ";
    }
    std::cout << "\n";
    std::cout << "the size of remain_node is " << n_node << std::endl;
*/
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
    delete ocp_rd[0];
    delete ocp_wr[0];
    ocp_rd[NEW_NUM] = new std::vector<int>();
    ocp_wr[NEW_NUM] = new std::vector<int>();

    for (time = 1; time < INSTNUM; time++) {
        //从wl取操作到ok_to_do，原则是新加入的操作写回地址不能与原有操作的写回地址重合（完全一致）
        addOkToDo(wl, ok_to_do);
        std::cout << "SUCCESS: add ok to do list at time " << time << endl;
/*      std::cout << "ok to do list is: " << endl;
        for (const OpPack& element : ok_to_do) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "> " << endl;;
        }*/
        /*
        std::cout << "waiting list is: " << endl;
        for (const OpPack& element : wl) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
        }
*/

        sortOkToDo(EleNodePointer, ok_to_do);
/*        std::cout << "after sort: ok to do list is: " << endl;
        for (const OpPack& element : ok_to_do) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "> " << endl;;
        }
*/
        vector <int>().swap(newly_valid);  //清除容器并最小化它的容量
        schedule(inst, ocp_rd, ocp_wr, EleNodePointer, ok_to_do, time, newly_valid, remain_node);
        std::cout << "SUCCESS: schedule at time " << time << endl;
/*
        for (int val : remain_node) 
        {
            std::cout << val << " ";
        }
        std::cout << "\n";
        std::cout << "the size of remain_node is " << remain_node.size() << std::endl;
*/
/*        std::cout << "ok to do list is: " << endl;
        for (const OpPack& element : ok_to_do) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "," << element.diag << "> " << endl;;
        }
*/
    //打印

    if (remain_node.size() <= NPE) {
    /*
        for (int i = 0; i < nnz_fill; i++) {
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
        sch2 = 1; //开启第二种调度
        delete ocp_rd[time];
        delete ocp_wr[time];
        ocp_rd[NEW_NUM + time] = new std::vector<int>();
        ocp_wr[NEW_NUM + time] = new std::vector<int>();
        break;
    }

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
        delete ocp_rd[time];
        delete ocp_wr[time];
        ocp_rd[NEW_NUM + time] = new std::vector<int>();
        ocp_wr[NEW_NUM + time] = new std::vector<int>();

        if ((!wl.size()) && (!ok_to_do.size()))
            break;

    }

    int n_node = remain_node.size();    
    if (!sch2) std::cout << "ERROR: fail to start the second schedule!\n";
    else {
        std::cout << "Begin: Second Schedule!\n";
        std::vector<std::vector<OpPack>*> nodes;
        std::vector<int>    node;
        
        std::cout << "ok to do list is: " << endl;
        for (const OpPack& element : ok_to_do) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "> " << endl;;
        }     

        std::cout << "waiting list is: " << endl;
        for (const OpPack& element : wl) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "> " << endl;
        }   

        for (int i = 0; i < n_node; i++) {
            node.push_back(remain_node[i]);
            nodes.push_back(new std::vector<OpPack>);
        }

        int evict_ok = evictList(ok_to_do, nodes, node);
        if (evict_ok == -1) return -1;
        evict_ok = evictList(wl, nodes, node);
        if (evict_ok == -1) return -1;
        evictTree(EleNodePointer, nodes, node, n_node);

        std::cout << "SUCCESS: evict! the nodes are \n";
        for (int i = 0; i < n_node; i++) {
            std::cout << i << " node: " << node[i] << std::endl;
            for (OpPack element : *(nodes[i])) {
                std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "> " << endl;
            }
        }

        //新建一个int向量pri，作为优先级标志
        std::vector<int> pri(n_node, 0);
        addPri(EleNodePointer, pri, nodes, node, n_node);
        std::cout << "the priority is: ";
        for (int val : pri)
        {
            std::cout << val << " ";
        }
        std::cout << std::endl;

        // 使用 sortByPriority 函数进行排序
        std::cout << "before sorted Results:\n";
        for (int i = 0; i < n_node; ++i) {
            std::cout << "Node: " << node[i] << std::endl;
            // 输出 nodes[i] 中的 OpPack
            for (const OpPack& element : *(nodes[i])) {
                std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "> " << endl;
            }
        }
        sortByPriority(node, nodes, pri);
        // 输出排序后的结果
        std::cout << "sorted Results:\n";
        for (int i = 0; i < n_node; ++i) {
            std::cout << "Node: " << node[i] << std::endl;
            // 输出 nodes[i] 中的 OpPack
            for (const OpPack& element : *(nodes[i])) {
                std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "> " << endl;
            }
        }

        std::vector<bool> only_div(n_node, 0);
        checkOnlyDiv(only_div, nodes, n_node);
        std::cout << "only_div: ";
        for (bool val : only_div) {
            std:: cout << val << " ";
        }
        std::cout << endl;

        std::vector<bool> ok_to_wb(n_node, 0); //0代表没有wb，1代表可以wb
        std::vector<bool> ok_to_sub(n_node, 0); //0代表没有sub，1代表可以sub
        std::vector<int> ok_to_wb_time(n_node);
        std::vector<int> regC_ready_time(n_node, 0);
        int sch2_time = time + 1;
        int current_n_node = n_node;
        //std::vector<std::vector<int>*> ocp_wb; 用ocp_wr替代掉了
        //for (int i = 0; i < INSTNUM - sch2_time; i++) {
            //ocp_wb.push_back(new std::vector<int>);
        //}

        std::cout << "sch2 time is " << sch2_time << std::endl;
        for (time = sch2_time; time < INSTNUM; time ++) {
            schedule2(inst, ocp_rd, ocp_wr, EleNodePointer, nodes, node, n_node, time, 
            only_div, ok_to_sub, ok_to_wb, ok_to_wb_time, regC_ready_time, &current_n_node);
            std::cout << "SUCCESS: schedule at time: " << time << std::endl;
            std::cout << "ok_to_sub: ";
            for (bool val : ok_to_sub)
            {
                std::cout << val << " ";
            }
            std::cout << std::endl;
            std::cout << "ok_to_wb: ";
            for (bool val : ok_to_wb)
            {
                std::cout << val << " ";
            }
            std::cout << std::endl;
            std::cout << "ok_to_wb_time: ";
            for (int val : ok_to_wb_time)
            {
                std::cout << val << " ";
            }
            std::cout << std::endl;

            delete ocp_rd[time];
            delete ocp_wr[time];
            ocp_rd[NEW_NUM + time] = new std::vector<int>();
            ocp_wr[NEW_NUM + time] = new std::vector<int>();

            if(!current_n_node) break;
        }

        // 释放分配的内存
        for (int i = time + 1; i <= NEW_NUM + time; i++) {
            delete ocp_rd[i];
            delete ocp_wr[i];
        }
        for (int i = 0; i < n_node; ++i) {
            delete nodes[i];
        }

    }

    std::cout << "Finished: schedule!\n";
    if ((time + 3) >= INSTNUM) {
        std::cout << "ERROR: instruction space is not enough!\n";
        printInst(inst, 0, INSTNUM - 1);

        std::cout << "ok to do list is: " << endl;
        for (const OpPack& element : ok_to_do) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "> " << endl;;
        }
        std::cout << "waiting list is: " << endl;
        for (const OpPack& element : wl) {
            std::cout << "<" << element.rs << "," << element.rt << "," << element.rd << "," << element.op << "> " << endl;;
        }
        
        int simulate_ok = simulate(inst, CAx_fill, INSTNUM, n_node);
        if (simulate_ok == 0) cout << "SUCCESS: simulation\n";

        cout <<"CSC format: after simulation" << endl; 
        printSparse(CAx_fill, CAi_fill, CAp_fill);

        //输出填充后的文件，方便matlab观察以及得到lu分解正确结果
        writeCSCtoMTX(CAx_fill, CAi_fill, CAp_fill, n, n, nnz_fill, result);


        // 释放每个元素的内存
        //for (int i = 0; i < INSTNUM; ++i) {
        //    delete ocp[i];
        //}

        // 释放数组的内存
        delete[] ocp_rd;
        delete[] ocp_wr;

        // 释放动态分配的内存
        for (int i = 0; i < nnz_fill; i++) {
            delete EleNodePointer[i];
        }

        for (int i = 0; i < INSTNUM; ++i) {
            delete[] inst[i];  // 释放每个内部数组
        }
        delete[] inst;  // 释放外部数组

        return 1;
    }

    printInst(inst, 0, time + 4);


    //输出指令
    //得到准确的指令周期
    int latency = getLat(inst, time + 3, time) + 1; //第一个没有指令的周期
    std::cout << "\nlatency = " << latency << std::endl;
    writeInst(inst, latency, inst_file1, inst_file2, inst_file3, inst_file4, inst_file5, count_file);
    //输出填充后的CAd_Ax_fill文件
    writeData(CAx_fill, nnz_fill, data_file);

    //写一个模拟验证执行的东西，得到最后的结果
    int simulate_ok = simulate(inst, CAx_fill, time + 4, n_node);
    if (simulate_ok == 0) cout << "SUCCESS: simulation\n";

    

    // 释放每个元素的内存
    //for (int i = 0; i < INSTNUM; ++i) {
        //delete ocp[i];
    //}

    // 释放数组的内存
    delete[] ocp_rd;
    delete[] ocp_wr;
    cout << "SUCCESS: simulation1\n";
    // 释放动态分配的内存
    for (int i = 0; i < nnz_fill; i++) {
        delete EleNodePointer[i];
    }
    cout << "SUCCESS: simulation3\n";
    for (int i = 0; i < INSTNUM; ++i) {
        delete[] inst[i];  // 释放每个内部数组
    }
    delete[] inst;  // 释放外部数组
    cout << "SUCCESS: simulation3\n";
/*
    cout <<"CSC format: after simulation" << endl; 
    printSparse(CAx_fill, CAi_fill, CAp_fill);
*/
    //输出填充后的文件，方便matlab观察以及得到lu分解正确结果
    writeCSCtoMTX(CAx_fill, CAi_fill, CAp_fill, n, n, nnz_fill, result);
    cout << "SUCCESS: simulation4\n";


    return 0;
}
