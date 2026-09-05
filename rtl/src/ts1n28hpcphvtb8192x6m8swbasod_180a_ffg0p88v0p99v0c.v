//*#*********************************************************************************************************************/
//*# Software       : TSMC MEMORY COMPILER tsn28hpcpd127spsram_2012.02.00.d.180a						*/
//*# Technology     : TSMC 28nm CMOS LOGIC High Performance Compact Mobile Computing Plus 1P10M HKMG CU_ELK 0.9V				*/
//*#  Memory Type    : TSMC 28nm High Performance Compact Mobile Computing Plus Single Port SRAM with d127 bit cell HVT periphery */
//*# Library Name   : ts1n28hpcphvtb8192x6m8swbasod (user specify : TS1N28HPCPHVTB8192X6M8SWBASOD)				*/
//*# Library Version: 180a												*/
//*# Generated Time : 2026/09/05, 20:07:41										*/
//*#*********************************************************************************************************************/
//*#															*/
//*# STATEMENT OF USE													*/
//*#															*/
//*# This information contains confidential and proprietary information of TSMC.					*/
//*# No part of this information may be reproduced, transmitted, transcribed,						*/
//*# stored in a retrieval system, or translated into any human or computer						*/
//*# language, in any form or by any means, electronic, mechanical, magnetic,						*/
//*# optical, chemical, manual, or otherwise, without the prior written permission					*/
//*# of TSMC. This information was prepared for informational purpose and is for					*/
//*# use by TSMC's customers only. TSMC reserves the right to make changes in the					*/
//*# information at any time and without notice.									*/
//*#															*/
//*#*********************************************************************************************************************/
//********************************************************************************/
//*                                                                              */
//*      Usage Limitation: PLEASE READ CAREFULLY FOR CORRECT USAGE               */
//*                                                                              */
//* The model doesn't support the control enable, data and address signals       */
//* transition at positive clock edge.                                           */
//* Please have some timing delays between control/data/address and clock signals*/
//* to ensure the correct behavior.                                              */
//*                                                                              */
//* Please be careful when using non 2^n  memory.                                */
//* In a non-fully decoded array, a write cycle to a nonexistent address location*/
//* does not change the memory array contents and output remains the same.       */
//* In a non-fully decoded array, a read cycle to a nonexistent address location */
//* does not change the memory array contents but the output becomes unknown.    */
//*                                                                              */
//* In the verilog model, the behavior of unknown clock will corrupt the         */
//* memory data and make output unknown regardless of CEB signal.  But in the    */
//* silicon, the unknown clock at CEB high, the memory and output data will be   */
//* held. The verilog model behavior is more conservative in this condition.     */
//*                                                                              */
//* The model doesn't identify physical column and row address.                  */
//*                                                                              */
//* The verilog model provides UNIT_DELAY mode for the fast function             */
//* simulation.                                                                  */
//* All timing values in the specification are not checked in the                */
//* UNIT_DELAY mode simulation.                                                  */
//* The model also provides NO_INPUT_FLOATING_CHECK mode to speed up simulation. */
//* However, it won't check floating input pins in standby mode.                 */
//*                                                                              */
//* Template Version : S_01_81401                                                */
//****************************************************************************** */
//*      Macro Usage       : (+define[MACRO] for Verilog compiliers)             */
//* +UNIT_DELAY : Enable fast function simulation.                               */
//* +no_warning : Disable all runtime warnings message from this model.          */
//* +TSMC_INITIALIZE_MEM : Initialize the memory data in verilog format.         */
//* +TSMC_INITIALIZE_FAULT : Initialize the memory fault data in verilog format. */
//* +TSMC_NO_TESTPINS_WARNING : Disable the wrong test pins connection error     */
//*                             message if necessary.                            */
//* +NO_INPUT_FLOATING_CHECK : Turn off floating check for all input pins in     */
//*                            standby mode.                                     */
//****************************************************************************** */
`resetall

`celldefine

`timescale 1ns/1ps
`delay_mode_path
`suppress_faults
`enable_portfaults

module TS1N28HPCPHVTB8192X6M8SWBASOD (
            SLP,
            SD,
            CLK, CEB, WEB,
            CEBM, WEBM,
            AWT,
            A, D,
            BWEB,
            AM, DM, 
            BWEBM,
            BIST,
            Q);

parameter numWord = 8192;
parameter numRow = 1024;
parameter numCM = 8;
parameter numIOBit = 6;
parameter numBit = 6;
parameter numWordAddr = 13;
parameter numRowAddr = 10;
parameter numCMAddr = 3;
parameter numRowRedSize = 0;
parameter numColRedSize = 0;
parameter numSRSize = numRowRedSize + numColRedSize;
parameter numRR = 2;
parameter numCR = 1;
parameter numDC = 0;
parameter numStuckAt = 20;

`ifdef UNIT_DELAY
parameter SRAM_DELAY = 0.0100;
`endif
`ifdef TSMC_INITIALIZE_MEM
parameter INITIAL_MEM_DELAY = 0.01;
`endif
`ifdef TSMC_INITIALIZE_FAULT
parameter INITIAL_FAULT_DELAY = 0.01;
`endif

`ifdef TSMC_INITIALIZE_MEM
parameter cdeFileInit  = "TS1N28HPCPHVTB8192X6M8SWBASOD_initial.cde";
`endif
`ifdef TSMC_INITIALIZE_FAULT
parameter cdeFileFault = "TS1N28HPCPHVTB8192X6M8SWBASOD_fault.cde";
`endif

//=== IO Ports ===//

// Mode Control
input BIST;
input AWT;
// Normal Mode Input
input SLP;
input SD;
input CLK;
input CEB;
input WEB;
input [12:0] A;
input [5:0] D;
input [5:0] BWEB;

// BIST Mode Input
input CEBM;
input WEBM;
input [12:0] AM;
input [5:0] DM;
input [5:0] BWEBM;

// Data Output
output [5:0] Q;


// Test Mode

//=== Internal Signals ===//
// Mode Control
wire BIST_i;
wire AWT_i;
        
// Normal Mode Input
wire SLP_i;
wire DSLP_i;
wire SD_i;
wire CLK_i;
wire CEB_i;
wire WEB_i;
wire [numWordAddr-1:0] A_i;
wire [numIOBit-1:0] D_i;
wire [numIOBit-1:0] BWEB_i;

// BIST Mode Input
wire CEBM_i;
wire WEBM_i;
wire [numWordAddr-1:0] AM_i;
wire [numIOBit-1:0] DM_i;
wire [numIOBit-1:0] BWEBM_i;

// Data Output
wire [numIOBit-1:0] Q_i;

// Serial Shift Register Data

// Test Mode

//=== IO Buffers ===//
// Mode Control
buf (BIST_i, BIST);
buf (AWT_i, AWT);
        
// Normal Mode Input
buf (SLP_i, SLP);
buf (SD_i, SD);
buf (CLK_i, CLK);
buf (CEB_i, CEB);
buf (WEB_i, WEB);
buf (A_i[0], A[0]);
buf (A_i[1], A[1]);
buf (A_i[2], A[2]);
buf (A_i[3], A[3]);
buf (A_i[4], A[4]);
buf (A_i[5], A[5]);
buf (A_i[6], A[6]);
buf (A_i[7], A[7]);
buf (A_i[8], A[8]);
buf (A_i[9], A[9]);
buf (A_i[10], A[10]);
buf (A_i[11], A[11]);
buf (A_i[12], A[12]);
buf (D_i[0], D[0]);
buf (D_i[1], D[1]);
buf (D_i[2], D[2]);
buf (D_i[3], D[3]);
buf (D_i[4], D[4]);
buf (D_i[5], D[5]);
buf (BWEB_i[0], BWEB[0]);
buf (BWEB_i[1], BWEB[1]);
buf (BWEB_i[2], BWEB[2]);
buf (BWEB_i[3], BWEB[3]);
buf (BWEB_i[4], BWEB[4]);
buf (BWEB_i[5], BWEB[5]);


// BIST Mode Input
buf (CEBM_i, CEBM);
buf (WEBM_i, WEBM);

buf (AM_i[0], AM[0]);
buf (AM_i[1], AM[1]);
buf (AM_i[2], AM[2]);
buf (AM_i[3], AM[3]);
buf (AM_i[4], AM[4]);
buf (AM_i[5], AM[5]);
buf (AM_i[6], AM[6]);
buf (AM_i[7], AM[7]);
buf (AM_i[8], AM[8]);
buf (AM_i[9], AM[9]);
buf (AM_i[10], AM[10]);
buf (AM_i[11], AM[11]);
buf (AM_i[12], AM[12]);
buf (DM_i[0], DM[0]);
buf (DM_i[1], DM[1]);
buf (DM_i[2], DM[2]);
buf (DM_i[3], DM[3]);
buf (DM_i[4], DM[4]);
buf (DM_i[5], DM[5]);
buf (BWEBM_i[0], BWEBM[0]);
buf (BWEBM_i[1], BWEBM[1]);
buf (BWEBM_i[2], BWEBM[2]);
buf (BWEBM_i[3], BWEBM[3]);
buf (BWEBM_i[4], BWEBM[4]);
buf (BWEBM_i[5], BWEBM[5]);

// Data Output
nmos (Q[0], Q_i[0], 1'b1);
nmos (Q[1], Q_i[1], 1'b1);
nmos (Q[2], Q_i[2], 1'b1);
nmos (Q[3], Q_i[3], 1'b1);
nmos (Q[4], Q_i[4], 1'b1);
nmos (Q[5], Q_i[5], 1'b1);



// Test Mode

//=== Data Structure ===//
reg [numBit-1:0] MEMORY[numRow-1:0][numCM-1:0];
reg [numBit-1:0] MEMORY_FAULT[numRow-1:0][numCM-1:0];
reg [numBit-1:0] RMEMORY [numRR-1:0][numCM-1:0];
reg [numIOBit-1:0] Q_d, Q_awt;
reg [numBit-1:0] Q_d_tmp;
reg [numIOBit-1:0] PRELOAD[0:numWord-1];

reg [numBit-1:0] DIN_tmp, ERR_tmp;
reg [numWordAddr-1:0] stuckAt0Addr [numStuckAt:0];
reg [numWordAddr-1:0] stuckAt1Addr [numStuckAt:0];
reg [numBit-1:0] stuckAt0Bit [numStuckAt:0];
reg [numBit-1:0] stuckAt1Bit [numStuckAt:0];

reg [numWordAddr-numCMAddr-1:0] row_tmp;
reg [numCMAddr-1:0] col_tmp;

integer i, j;
reg read_flag, write_flag, idle_flag;
reg slp_mode;
reg dslp_mode;
reg sd_mode;
reg clk_latch;

`ifdef UNIT_DELAY
`else
reg notify_sd;
reg notify_awt_sd;
reg notify_slp;
reg notify_awt_slp;
reg notify_clk;
reg notify_bist;
reg notify_ceb;
reg notify_web;
reg notify_addr;
reg notify_din;
reg notify_bweb;
`endif    //end `ifdef UNIT_DELAY

reg CEBL;
reg WEBL;

wire iCEB=((BIST_i===1) ? CEBM_i : ((BIST_i===0)?CEB_i : 1'bx));
wire iWEB = (BIST_i===1) ? WEBM_i : ((BIST_i===0)? WEB_i: 1'bx);
wire [numWordAddr-1:0] iA = (BIST_i===1) ? AM_i : ((BIST_i===0)? A_i: {{numWordAddr}{1'bx}});

reg [numWordAddr-numCMAddr-1:0] iRowAddr;
reg [numCMAddr-1:0] iColAddr;
wire [numIOBit-1:0] iD = BIST_i ? DM_i : D_i;
wire [numIOBit-1:0] iBWEB = BIST_i ? BWEBM_i : BWEB_i;


assign DSLP_i=1'b0;

`ifdef UNIT_DELAY
`else
wire check_read = read_flag;
wire check_write = write_flag;
wire check_nosd= ~SD;
wire check_nodslp= 1'b1;
wire check_noslp= ~SLP;
wire check_nosd_nodslp = ~SD_i & ~DSLP_i;
wire check_nopd = ~SD_i & ~DSLP_i & ~SLP_i;
wire check_noidle = ~idle_flag & ~SD_i & ~DSLP_i & ~SLP_i;

wire check_awt_norm = AWT_i & !BIST;
wire check_awt_bist = AWT_i & BIST;
wire check_nosd_nodslp_norm = check_nosd_nodslp & !BIST;
wire check_nosd_nodslp_bist = check_nosd_nodslp & BIST;
wire check_read_norm = check_read & !BIST;
wire check_read_bist = check_read & BIST;
wire check_write_norm = check_write & !BIST;
wire check_write_bist = check_write & BIST;
wire check_noidle_norm = check_noidle & !BIST;
wire check_noidle_bist = check_noidle & BIST;
wire check_nopd_norm = check_nopd & !BIST;
wire check_nopd_bist = check_nopd & BIST;
`endif    //end `ifdef UNIT_DELAY
assign Q_i=((AWT_i===1 && ~SD_i && ~DSLP_i && ~SLP_i)? Q_awt :  Q_d );

`ifdef UNIT_DELAY
parameter tSDQ = 1.9556;
parameter tSLPQ = 1.9556;
`else

specify
    specparam PATHPULSE$ = ( 0, 0.001 );

    specparam tCYC = 0.5476;
    specparam tCKH = 0.1105;
    specparam tCKL = 0.1437;
    specparam tCS = 0.1439;
    specparam tCH = 0.0456;
    specparam tWS = 0.0914;
    specparam tWH = 0.0517;
    specparam tAS = 0.1083;
    specparam tAH = 0.0555;
    specparam tDS = 0.0870;
    specparam tDH = 0.0398;
    specparam tCD = 0.4997;
`ifdef TSMC_CM_READ_X_SQUASHING
    specparam tHOLD = 0.4997;
`else    
    specparam tHOLD = 0.3926;
`endif    
    specparam tQH = 0.0000;

    specparam tSDWK = 7.1837;
    specparam tSDWK2CLK = 7.1837;
    specparam tSD = 0.5476;
    specparam tXSD = 0.1275;
    specparam tSDX = 1.0555;
    specparam tSDQ = 1.9556;
    specparam tSDQH = 0.0000;
    specparam tSLPWK = 0.7333;
    specparam tSLPWK2CLK = 0.7333;
    specparam tSLP = 0.5476;
    specparam tXSLP = 0.1275;
    specparam tSLPX = 1.0596;
    specparam tSLPQ = 1.9556;
    specparam tSLPQH = 0.0000;

    specparam tBISTS = 0.2102;
    specparam tBISTH = 0.0315;
    specparam tCMS = 0.1439;
    specparam tCMH = 0.0456;
    specparam tWMS = 0.0914;
    specparam tWMH = 0.0517;
    specparam tAMS = 0.1083;
    specparam tAMH = 0.0555;
    specparam tDMS = 0.0870;
    specparam tDMH = 0.0398;
    specparam tBWS = 0.0956;
    specparam tBWH = 0.0371;
    specparam tBWMS = 0.0956;
    specparam tBWMH = 0.0371;


    specparam tAWTQ = 0.1616;
    specparam tAWTQH = 0.1104;
    specparam tDQ = 0.2985;
    specparam tDQH = 0.1232;
    specparam tBWEBQ = 0.2985;
    specparam tBWEBQH = 0.1232;
    specparam tDMQ = 0.2985;
    specparam tDMQH = 0.1232;
    specparam tBWEBMQ = 0.2985;
    specparam tBWEBMQH = 0.1232;

    if(!SD & !SLP & AWT) (posedge AWT => (Q[0] : 1'bx)) = (tAWTQ, tAWTQ, tAWTQH, tAWTQ, tAWTQH, tAWTQ);
    if(!SD & !SLP & AWT) (posedge AWT => (Q[1] : 1'bx)) = (tAWTQ, tAWTQ, tAWTQH, tAWTQ, tAWTQH, tAWTQ);
    if(!SD & !SLP & AWT) (posedge AWT => (Q[2] : 1'bx)) = (tAWTQ, tAWTQ, tAWTQH, tAWTQ, tAWTQH, tAWTQ);
    if(!SD & !SLP & AWT) (posedge AWT => (Q[3] : 1'bx)) = (tAWTQ, tAWTQ, tAWTQH, tAWTQ, tAWTQH, tAWTQ);
    if(!SD & !SLP & AWT) (posedge AWT => (Q[4] : 1'bx)) = (tAWTQ, tAWTQ, tAWTQH, tAWTQ, tAWTQH, tAWTQ);
    if(!SD & !SLP & AWT) (posedge AWT => (Q[5] : 1'bx)) = (tAWTQ, tAWTQ, tAWTQH, tAWTQ, tAWTQH, tAWTQ);
    if(!SD & !SLP & AWT & !BIST) (posedge D[0] => (Q[0] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (negedge D[0] => (Q[0] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (posedge D[1] => (Q[1] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (negedge D[1] => (Q[1] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (posedge D[2] => (Q[2] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (negedge D[2] => (Q[2] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (posedge D[3] => (Q[3] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (negedge D[3] => (Q[3] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (posedge D[4] => (Q[4] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (negedge D[4] => (Q[4] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (posedge D[5] => (Q[5] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (negedge D[5] => (Q[5] : 1'bx)) = (tDQ, tDQ, tDQH, tDQ, tDQH, tDQ);
    if(!SD & !SLP & AWT & !BIST) (posedge BWEB[0] => (Q[0] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & !BIST) (negedge BWEB[0] => (Q[0] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & !BIST) (posedge BWEB[1] => (Q[1] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & !BIST) (negedge BWEB[1] => (Q[1] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & !BIST) (posedge BWEB[2] => (Q[2] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & !BIST) (negedge BWEB[2] => (Q[2] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & !BIST) (posedge BWEB[3] => (Q[3] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & !BIST) (negedge BWEB[3] => (Q[3] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & !BIST) (posedge BWEB[4] => (Q[4] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & !BIST) (negedge BWEB[4] => (Q[4] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & !BIST) (posedge BWEB[5] => (Q[5] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & !BIST) (negedge BWEB[5] => (Q[5] : 1'bx)) = (tBWEBQ, tBWEBQ, tBWEBQH, tBWEBQ, tBWEBQH, tBWEBQ);
    if(!SD & !SLP & AWT & BIST) (posedge DM[0] => (Q[0] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (negedge DM[0] => (Q[0] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (posedge DM[1] => (Q[1] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (negedge DM[1] => (Q[1] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (posedge DM[2] => (Q[2] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (negedge DM[2] => (Q[2] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (posedge DM[3] => (Q[3] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (negedge DM[3] => (Q[3] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (posedge DM[4] => (Q[4] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (negedge DM[4] => (Q[4] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (posedge DM[5] => (Q[5] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (negedge DM[5] => (Q[5] : 1'bx)) = (tDMQ, tDMQ, tDMQH, tDMQ, tDMQH, tDMQ);
    if(!SD & !SLP & AWT & BIST) (posedge BWEBM[0] => (Q[0] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);
    if(!SD & !SLP & AWT & BIST) (negedge BWEBM[0] => (Q[0] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);
    if(!SD & !SLP & AWT & BIST) (posedge BWEBM[1] => (Q[1] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);
    if(!SD & !SLP & AWT & BIST) (negedge BWEBM[1] => (Q[1] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);
    if(!SD & !SLP & AWT & BIST) (posedge BWEBM[2] => (Q[2] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);
    if(!SD & !SLP & AWT & BIST) (negedge BWEBM[2] => (Q[2] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);
    if(!SD & !SLP & AWT & BIST) (posedge BWEBM[3] => (Q[3] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);
    if(!SD & !SLP & AWT & BIST) (negedge BWEBM[3] => (Q[3] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);
    if(!SD & !SLP & AWT & BIST) (posedge BWEBM[4] => (Q[4] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);
    if(!SD & !SLP & AWT & BIST) (negedge BWEBM[4] => (Q[4] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);
    if(!SD & !SLP & AWT & BIST) (posedge BWEBM[5] => (Q[5] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);
    if(!SD & !SLP & AWT & BIST) (negedge BWEBM[5] => (Q[5] : 1'bx)) = (tBWEBMQ, tBWEBMQ, tBWEBMQH, tBWEBMQ, tBWEBMQH, tBWEBMQ);

    if (!SD & !SLP & !AWT & BIST & !CEBM & WEBM) (posedge CLK => (Q[0] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);
    if (!SD & !SLP & !AWT & !BIST & !CEB & WEB) (posedge CLK => (Q[0] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);
    if (!SD & !SLP & !AWT & BIST & !CEBM & WEBM) (posedge CLK => (Q[1] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);
    if (!SD & !SLP & !AWT & !BIST & !CEB & WEB) (posedge CLK => (Q[1] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);
    if (!SD & !SLP & !AWT & BIST & !CEBM & WEBM) (posedge CLK => (Q[2] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);
    if (!SD & !SLP & !AWT & !BIST & !CEB & WEB) (posedge CLK => (Q[2] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);
    if (!SD & !SLP & !AWT & BIST & !CEBM & WEBM) (posedge CLK => (Q[3] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);
    if (!SD & !SLP & !AWT & !BIST & !CEB & WEB) (posedge CLK => (Q[3] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);
    if (!SD & !SLP & !AWT & BIST & !CEBM & WEBM) (posedge CLK => (Q[4] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);
    if (!SD & !SLP & !AWT & !BIST & !CEB & WEB) (posedge CLK => (Q[4] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);
    if (!SD & !SLP & !AWT & BIST & !CEBM & WEBM) (posedge CLK => (Q[5] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);
    if (!SD & !SLP & !AWT & !BIST & !CEB & WEB) (posedge CLK => (Q[5] : 1'bx)) = (tCD, tCD, tHOLD, tCD, tHOLD, tCD);


    (posedge SD => (Q[0] : 1'bx)) = (0,tSDQ,tSDQH,0,tSDQH,tSDQ);
    (negedge SD => (Q[0] : 1'bx)) = (0,0,tQH,0,tQH,0);
    (posedge SD => (Q[1] : 1'bx)) = (0,tSDQ,tSDQH,0,tSDQH,tSDQ);
    (negedge SD => (Q[1] : 1'bx)) = (0,0,tQH,0,tQH,0);
    (posedge SD => (Q[2] : 1'bx)) = (0,tSDQ,tSDQH,0,tSDQH,tSDQ);
    (negedge SD => (Q[2] : 1'bx)) = (0,0,tQH,0,tQH,0);
    (posedge SD => (Q[3] : 1'bx)) = (0,tSDQ,tSDQH,0,tSDQH,tSDQ);
    (negedge SD => (Q[3] : 1'bx)) = (0,0,tQH,0,tQH,0);
    (posedge SD => (Q[4] : 1'bx)) = (0,tSDQ,tSDQH,0,tSDQH,tSDQ);
    (negedge SD => (Q[4] : 1'bx)) = (0,0,tQH,0,tQH,0);
    (posedge SD => (Q[5] : 1'bx)) = (0,tSDQ,tSDQH,0,tSDQH,tSDQ);
    (negedge SD => (Q[5] : 1'bx)) = (0,0,tQH,0,tQH,0);


    if(!SD) (posedge SLP => (Q[0] : 1'bx)) = (0,tSLPQ,tSLPQH,0,tSLPQH,tSLPQ);
    if(!SD) (negedge SLP => (Q[0] : 1'bx)) = (0,0,tQH,0,tQH,0);
    if(!SD) (posedge SLP => (Q[1] : 1'bx)) = (0,tSLPQ,tSLPQH,0,tSLPQH,tSLPQ);
    if(!SD) (negedge SLP => (Q[1] : 1'bx)) = (0,0,tQH,0,tQH,0);
    if(!SD) (posedge SLP => (Q[2] : 1'bx)) = (0,tSLPQ,tSLPQH,0,tSLPQH,tSLPQ);
    if(!SD) (negedge SLP => (Q[2] : 1'bx)) = (0,0,tQH,0,tQH,0);
    if(!SD) (posedge SLP => (Q[3] : 1'bx)) = (0,tSLPQ,tSLPQH,0,tSLPQH,tSLPQ);
    if(!SD) (negedge SLP => (Q[3] : 1'bx)) = (0,0,tQH,0,tQH,0);
    if(!SD) (posedge SLP => (Q[4] : 1'bx)) = (0,tSLPQ,tSLPQH,0,tSLPQH,tSLPQ);
    if(!SD) (negedge SLP => (Q[4] : 1'bx)) = (0,0,tQH,0,tQH,0);
    if(!SD) (posedge SLP => (Q[5] : 1'bx)) = (0,tSLPQ,tSLPQH,0,tSLPQH,tSLPQ);
    if(!SD) (negedge SLP => (Q[5] : 1'bx)) = (0,0,tQH,0,tQH,0);

    $setuphold(negedge CEB &&& ~BIST, negedge SD, tSDWK,0, notify_sd);
    $setuphold(posedge CEB &&& ~BIST, posedge SD, 0,tSD, notify_sd);
    $setuphold(negedge CEBM &&& BIST, negedge SD, tSDWK,0, notify_sd);
    $setuphold(posedge CEBM &&& BIST, posedge SD, 0,tSD, notify_sd);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge SD, tSDWK2CLK,0, notify_sd);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge SD, tSDWK2CLK,0, notify_sd);
    $setuphold(negedge CEB &&& ~BIST, negedge SLP, tSLPWK,0, notify_slp);
    $setuphold(posedge CEB &&& ~BIST, posedge SLP, 0,tSLP, notify_slp);
    $setuphold(negedge CEBM &&& BIST, negedge SLP, tSLPWK,0, notify_slp);
    $setuphold(posedge CEBM &&& BIST, posedge SLP, 0,tSLP, notify_slp);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge SLP, tSLPWK2CLK,0, notify_slp);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge SLP, tSLPWK2CLK,0, notify_slp);

    $period(posedge CLK &&& ~CEB, tCYC, notify_clk);
    $width(posedge CLK &&& ~CEB, tCKH, 0, notify_clk);
    $width(negedge CLK &&& ~CEB, tCKL, 0, notify_clk);

    $setuphold(posedge CLK &&& check_nopd, negedge BIST, tBISTS, tBISTH, notify_bist);
    $setuphold(posedge CLK &&& check_nopd, posedge BIST, tBISTS, tBISTH, notify_bist);
    $setuphold(posedge CLK &&& check_nopd_norm, negedge CEB, tCS, tCH, notify_ceb);
    $setuphold(posedge CLK &&& check_nopd_norm, posedge CEB, tCS, tCH, notify_ceb);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge WEB, tWS, tWH, notify_web);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge WEB, tWS, tWH, notify_web);

    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[0], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[1], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[2], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[3], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[4], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[5], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[6], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[7], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[8], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[9], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[10], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[11], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, negedge A[12], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[0], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[1], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[2], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[3], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[4], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[5], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[6], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[7], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[8], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[9], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[10], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[11], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_norm, posedge A[12], tAS, tAH, notify_addr);
    $setuphold(posedge CLK &&& check_write_norm, negedge D[0], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, negedge D[1], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, negedge D[2], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, negedge D[3], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, negedge D[4], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, negedge D[5], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, posedge D[0], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, posedge D[1], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, posedge D[2], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, posedge D[3], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, posedge D[4], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, posedge D[5], tDS, tDH, notify_din);
    $setuphold(posedge CLK &&& check_write_norm, negedge BWEB[0], tBWS, tBWH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_norm, negedge BWEB[1], tBWS, tBWH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_norm, negedge BWEB[2], tBWS, tBWH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_norm, negedge BWEB[3], tBWS, tBWH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_norm, negedge BWEB[4], tBWS, tBWH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_norm, negedge BWEB[5], tBWS, tBWH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_norm, posedge BWEB[0], tBWS, tBWH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_norm, posedge BWEB[1], tBWS, tBWH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_norm, posedge BWEB[2], tBWS, tBWH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_norm, posedge BWEB[3], tBWS, tBWH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_norm, posedge BWEB[4], tBWS, tBWH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_norm, posedge BWEB[5], tBWS, tBWH, notify_bweb);

    $period(posedge CLK &&& CEB, tCYC, notify_clk);
    $width(posedge CLK &&& CEB, tCKH, 0, notify_clk);
    $width(negedge CLK &&& CEB, tCKL, 0, notify_clk);

    $setuphold(posedge CLK &&& check_nopd_bist, negedge CEBM, tCMS, tCMH, notify_ceb);
    $setuphold(posedge CLK &&& check_nopd_bist, posedge CEBM, tCMS, tCMH, notify_ceb);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge WEBM, tWMS, tWMH, notify_web);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge WEBM, tWMS, tWMH, notify_web);

    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[0], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[1], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[2], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[3], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[4], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[5], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[6], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[7], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[8], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[9], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[10], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[11], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, negedge AM[12], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[0], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[1], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[2], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[3], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[4], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[5], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[6], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[7], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[8], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[9], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[10], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[11], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_noidle_bist, posedge AM[12], tAMS, tAMH, notify_addr);
    $setuphold(posedge CLK &&& check_write_bist, negedge DM[0], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, negedge DM[1], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, negedge DM[2], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, negedge DM[3], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, negedge DM[4], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, negedge DM[5], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, posedge DM[0], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, posedge DM[1], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, posedge DM[2], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, posedge DM[3], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, posedge DM[4], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, posedge DM[5], tDMS, tDMH, notify_din);
    $setuphold(posedge CLK &&& check_write_bist, negedge BWEBM[0], tBWMS, tBWMH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_bist, negedge BWEBM[1], tBWMS, tBWMH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_bist, negedge BWEBM[2], tBWMS, tBWMH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_bist, negedge BWEBM[3], tBWMS, tBWMH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_bist, negedge BWEBM[4], tBWMS, tBWMH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_bist, negedge BWEBM[5], tBWMS, tBWMH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_bist, posedge BWEBM[0], tBWMS, tBWMH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_bist, posedge BWEBM[1], tBWMS, tBWMH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_bist, posedge BWEBM[2], tBWMS, tBWMH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_bist, posedge BWEBM[3], tBWMS, tBWMH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_bist, posedge BWEBM[4], tBWMS, tBWMH, notify_bweb);
    $setuphold(posedge CLK &&& check_write_bist, posedge BWEBM[5], tBWMS, tBWMH, notify_bweb);



    $setuphold(edge[0x] CLK_i , posedge SD, tSDX, 0, notify_clk);
    $setuphold(edge[1x] CLK_i , posedge SD, tSDX, 0, notify_clk);
    $setuphold(edge[x0] CLK_i , negedge SD, 0, tXSD, notify_clk);
    $setuphold(edge[x1] CLK_i , negedge SD, 0, tXSD, notify_clk);
    $setuphold(edge[0x] AWT_i , posedge SD, tSDX, 0, notify_clk);
    $setuphold(edge[1x] AWT_i , posedge SD, tSDX, 0, notify_clk);
    $setuphold(edge[x0] AWT_i , negedge SD, 0, tXSD, notify_clk);
    $setuphold(edge[x1] AWT_i , negedge SD, 0, tXSD, notify_clk);
    $setuphold(edge[0x] SLP_i , posedge SD, tSDX, 0, notify_clk);
    $setuphold(edge[1x] SLP_i , posedge SD, tSDX, 0, notify_clk);
    $setuphold(edge[x0] SLP_i , negedge SD, 0, tXSD, notify_clk);
    $setuphold(edge[x1] SLP_i , negedge SD, 0, tXSD, notify_clk);
    
    $setuphold(edge[0x] BIST_i , posedge SD, tSDX, 0, notify_clk);
    $setuphold(edge[1x] BIST_i , posedge SD, tSDX, 0, notify_clk);
    $setuphold(edge[x0] BIST_i , negedge SD, 0, tXSD, notify_clk);
    $setuphold(edge[x1] BIST_i , negedge SD, 0, tXSD, notify_clk);
    $setuphold(edge[0x] AM_i[0] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[0] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[0] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[0] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[0] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[0] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[0] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[0] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[1] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[1] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[1] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[1] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[1] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[1] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[1] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[1] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[2] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[2] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[2] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[2] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[2] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[2] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[2] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[2] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[3] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[3] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[3] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[3] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[3] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[3] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[3] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[3] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[4] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[4] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[4] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[4] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[4] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[4] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[4] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[4] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[5] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[5] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[5] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[5] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[5] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[5] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[5] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[5] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[6] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[6] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[6] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[6] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[6] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[6] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[6] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[6] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[7] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[7] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[7] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[7] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[7] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[7] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[7] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[7] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[8] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[8] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[8] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[8] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[8] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[8] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[8] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[8] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[9] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[9] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[9] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[9] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[9] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[9] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[9] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[9] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[10] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[10] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[10] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[10] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[10] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[10] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[10] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[10] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[11] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[11] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[11] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[11] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[11] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[11] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[11] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[11] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] AM_i[12] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[12] &&& BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[12] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] AM_i[12] &&& BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] A_i[12] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[1x] A_i[12] &&& ~BIST_i , posedge SD, tSDX, 0, notify_addr);
    $setuphold(edge[x0] A_i[12] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[x1] A_i[12] &&& ~BIST_i , negedge SD, 0, tXSD, notify_addr);
    $setuphold(edge[0x] DM_i[0] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] DM_i[0] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] DM_i[0] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] DM_i[0] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] D_i[0] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] D_i[0] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] D_i[0] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] D_i[0] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] BWEBM_i[0] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[0] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[0] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[0] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] BWEB_i[0] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[0] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[0] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEB_i[0] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] DM_i[1] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] DM_i[1] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] DM_i[1] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] DM_i[1] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] D_i[1] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] D_i[1] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] D_i[1] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] D_i[1] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] BWEBM_i[1] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[1] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[1] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[1] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] BWEB_i[1] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[1] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[1] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEB_i[1] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] DM_i[2] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] DM_i[2] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] DM_i[2] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] DM_i[2] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] D_i[2] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] D_i[2] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] D_i[2] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] D_i[2] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] BWEBM_i[2] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[2] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[2] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[2] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] BWEB_i[2] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[2] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[2] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEB_i[2] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] DM_i[3] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] DM_i[3] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] DM_i[3] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] DM_i[3] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] D_i[3] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] D_i[3] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] D_i[3] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] D_i[3] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] BWEBM_i[3] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[3] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[3] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[3] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] BWEB_i[3] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[3] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[3] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEB_i[3] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] DM_i[4] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] DM_i[4] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] DM_i[4] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] DM_i[4] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] D_i[4] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] D_i[4] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] D_i[4] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] D_i[4] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] BWEBM_i[4] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[4] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[4] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[4] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] BWEB_i[4] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[4] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[4] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEB_i[4] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] DM_i[5] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] DM_i[5] &&& BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] DM_i[5] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] DM_i[5] &&& BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] D_i[5] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[1x] D_i[5] &&& ~BIST_i , posedge SD, tSDX, 0, notify_din);
    $setuphold(edge[x0] D_i[5] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[x1] D_i[5] &&& ~BIST_i , negedge SD, 0, tXSD, notify_din);
    $setuphold(edge[0x] BWEBM_i[5] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[5] &&& BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[5] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[5] &&& BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] BWEB_i[5] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[5] &&& ~BIST_i , posedge SD, tSDX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[5] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[x1] BWEB_i[5] &&& ~BIST_i , negedge SD, 0, tXSD, notify_bweb);
    $setuphold(edge[0x] CEBM_i &&& BIST_i , posedge SD, tSDX, 0, notify_ceb);
    $setuphold(edge[1x] CEBM_i &&& BIST_i , posedge SD, tSDX, 0, notify_ceb);
    $setuphold(edge[x0] CEBM_i &&& BIST_i , negedge SD, 0, tXSD, notify_ceb);
    $setuphold(edge[x1] CEBM_i &&& BIST_i , negedge SD, 0, tXSD, notify_ceb);
    $setuphold(edge[0x] WEBM_i &&& BIST_i , posedge SD, tSDX, 0, notify_web);
    $setuphold(edge[1x] WEBM_i &&& BIST_i , posedge SD, tSDX, 0, notify_web);
    $setuphold(edge[x0] WEBM_i &&& BIST_i , negedge SD, 0, tXSD, notify_web);
    $setuphold(edge[x1] WEBM_i &&& BIST_i , negedge SD, 0, tXSD, notify_web);
    $setuphold(edge[0x] CEB_i &&& ~BIST_i , posedge SD, tSDX, 0, notify_ceb);
    $setuphold(edge[1x] CEB_i &&& ~BIST_i , posedge SD, tSDX, 0, notify_ceb);
    $setuphold(edge[x0] CEB_i &&& ~BIST_i , negedge SD, 0, tXSD, notify_ceb);
    $setuphold(edge[x1] CEB_i &&& ~BIST_i , negedge SD, 0, tXSD, notify_ceb);
    $setuphold(edge[0x] WEB_i &&& ~BIST_i , posedge SD, tSDX, 0, notify_web);
    $setuphold(edge[1x] WEB_i &&& ~BIST_i , posedge SD, tSDX, 0, notify_web);
    $setuphold(edge[x0] WEB_i &&& ~BIST_i , negedge SD, 0, tXSD, notify_web);
    $setuphold(edge[x1] WEB_i &&& ~BIST_i , negedge SD, 0, tXSD, notify_web);

    $setuphold(edge[0x] CLK_i &&& check_nosd_nodslp , posedge SLP, tSLPX, 0, notify_clk);
    $setuphold(edge[1x] CLK_i &&& check_nosd_nodslp , posedge SLP, tSLPX, 0, notify_clk);
    $setuphold(edge[x0] CLK_i &&& check_nosd_nodslp , negedge SLP, 0, tXSLP, notify_clk);
    $setuphold(edge[x1] CLK_i &&& check_nosd_nodslp , negedge SLP, 0, tXSLP, notify_clk);
    $setuphold(edge[0x] AWT_i &&& check_nosd_nodslp , posedge SLP, tSLPX, 0, notify_clk);
    $setuphold(edge[1x] AWT_i &&& check_nosd_nodslp , posedge SLP, tSLPX, 0, notify_clk);
    $setuphold(edge[x0] AWT_i &&& check_nosd_nodslp , negedge SLP, 0, tXSLP, notify_clk);
    $setuphold(edge[x1] AWT_i &&& check_nosd_nodslp , negedge SLP, 0, tXSLP, notify_clk);
    
    $setuphold(edge[0x] BIST_i &&& check_nosd_nodslp , posedge SLP, tSLPX, 0, notify_clk);
    $setuphold(edge[1x] BIST_i &&& check_nosd_nodslp , posedge SLP, tSLPX, 0, notify_clk);
    $setuphold(edge[x0] BIST_i &&& check_nosd_nodslp , negedge SLP, 0, tXSLP, notify_clk);
    $setuphold(edge[x1] BIST_i &&& check_nosd_nodslp , negedge SLP, 0, tXSLP, notify_clk);
    $setuphold(edge[0x] AM_i[0] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[0] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[0] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[0] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[0] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[0] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[0] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[0] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[1] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[1] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[1] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[1] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[1] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[1] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[1] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[1] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[2] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[2] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[2] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[2] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[2] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[2] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[2] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[2] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[3] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[3] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[3] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[3] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[3] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[3] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[3] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[3] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[4] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[4] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[4] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[4] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[4] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[4] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[4] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[4] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[5] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[5] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[5] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[5] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[5] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[5] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[5] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[5] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[6] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[6] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[6] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[6] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[6] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[6] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[6] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[6] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[7] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[7] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[7] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[7] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[7] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[7] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[7] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[7] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[8] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[8] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[8] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[8] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[8] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[8] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[8] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[8] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[9] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[9] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[9] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[9] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[9] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[9] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[9] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[9] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[10] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[10] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[10] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[10] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[10] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[10] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[10] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[10] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[11] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[11] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[11] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[11] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[11] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[11] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[11] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[11] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] AM_i[12] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] AM_i[12] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] AM_i[12] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] AM_i[12] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] A_i[12] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[1x] A_i[12] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_addr);
    $setuphold(edge[x0] A_i[12] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[x1] A_i[12] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_addr);
    $setuphold(edge[0x] DM_i[0] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] DM_i[0] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] DM_i[0] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] DM_i[0] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] D_i[0] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] D_i[0] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] D_i[0] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] D_i[0] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] BWEBM_i[0] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[0] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[0] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[0] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] BWEB_i[0] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[0] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[0] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEB_i[0] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] DM_i[1] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] DM_i[1] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] DM_i[1] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] DM_i[1] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] D_i[1] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] D_i[1] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] D_i[1] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] D_i[1] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] BWEBM_i[1] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[1] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[1] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[1] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] BWEB_i[1] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[1] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[1] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEB_i[1] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] DM_i[2] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] DM_i[2] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] DM_i[2] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] DM_i[2] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] D_i[2] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] D_i[2] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] D_i[2] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] D_i[2] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] BWEBM_i[2] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[2] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[2] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[2] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] BWEB_i[2] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[2] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[2] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEB_i[2] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] DM_i[3] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] DM_i[3] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] DM_i[3] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] DM_i[3] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] D_i[3] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] D_i[3] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] D_i[3] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] D_i[3] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] BWEBM_i[3] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[3] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[3] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[3] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] BWEB_i[3] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[3] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[3] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEB_i[3] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] DM_i[4] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] DM_i[4] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] DM_i[4] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] DM_i[4] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] D_i[4] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] D_i[4] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] D_i[4] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] D_i[4] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] BWEBM_i[4] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[4] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[4] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[4] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] BWEB_i[4] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[4] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[4] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEB_i[4] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] DM_i[5] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] DM_i[5] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] DM_i[5] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] DM_i[5] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] D_i[5] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[1x] D_i[5] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_din);
    $setuphold(edge[x0] D_i[5] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[x1] D_i[5] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_din);
    $setuphold(edge[0x] BWEBM_i[5] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEBM_i[5] &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEBM_i[5] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEBM_i[5] &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] BWEB_i[5] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[1x] BWEB_i[5] &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_bweb);
    $setuphold(edge[x0] BWEB_i[5] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[x1] BWEB_i[5] &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_bweb);
    $setuphold(edge[0x] CEBM_i &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_ceb);
    $setuphold(edge[1x] CEBM_i &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_ceb);
    $setuphold(edge[x0] CEBM_i &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_ceb);
    $setuphold(edge[x1] CEBM_i &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_ceb);
    $setuphold(edge[0x] WEBM_i &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_web);
    $setuphold(edge[1x] WEBM_i &&& check_nosd_nodslp_bist , posedge SLP, tSLPX, 0, notify_web);
    $setuphold(edge[x0] WEBM_i &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_web);
    $setuphold(edge[x1] WEBM_i &&& check_nosd_nodslp_bist , negedge SLP, 0, tXSLP, notify_web);
    $setuphold(edge[0x] CEB_i &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_ceb);
    $setuphold(edge[1x] CEB_i &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_ceb);
    $setuphold(edge[x0] CEB_i &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_ceb);
    $setuphold(edge[x1] CEB_i &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_ceb);
    $setuphold(edge[0x] WEB_i &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_web);
    $setuphold(edge[1x] WEB_i &&& check_nosd_nodslp_norm , posedge SLP, tSLPX, 0, notify_web);
    $setuphold(edge[x0] WEB_i &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_web);
    $setuphold(edge[x1] WEB_i &&& check_nosd_nodslp_norm , negedge SLP, 0, tXSLP, notify_web);

endspecify
`endif    //end `ifdef UNIT_DELAY

initial begin
    read_flag = 0;
    write_flag = 0;
    idle_flag = 0;
    slp_mode = 0;
    dslp_mode=0;
    sd_mode=0;
end

 `ifdef TSMC_INITIALIZE_MEM
initial begin 
`ifdef TSMC_INITIALIZE_FORMAT_BINARY
     #(INITIAL_MEM_DELAY)  $readmemb(cdeFileInit, PRELOAD, 0, numWord-1);
`else
     #(INITIAL_MEM_DELAY)  $readmemh(cdeFileInit, PRELOAD, 0, numWord-1);
`endif
    for (i = 0; i < numWord; i = i + 1) begin
        {row_tmp, col_tmp} = i;
        MEMORY[row_tmp][col_tmp] = PRELOAD[i];
    end
end
`endif //  `ifdef TSMC_INITIALIZE_MEM
   
`ifdef TSMC_INITIALIZE_FAULT
initial begin
`ifdef TSMC_INITIALIZE_FORMAT_BINARY
     #(INITIAL_FAULT_DELAY) $readmemb(cdeFileFault, PRELOAD, 0, numWord-1);
`else
     #(INITIAL_FAULT_DELAY) $readmemh(cdeFileFault, PRELOAD, 0, numWord-1);
`endif
    for (i = 0; i < numWord; i = i + 1) begin
        {row_tmp, col_tmp} = i;
        MEMORY_FAULT[row_tmp][col_tmp] = PRELOAD[i];
    end
end
`endif //  `ifdef TSMC_INITIALIZE_FAULT


`ifdef TSMC_NO_TESTPINS_WARNING
`else
`endif

always @(BIST_i) begin
    if ((BIST_i === 1'bx || BIST_i === 1'bz) && !SD_i && !DSLP_i && !SLP_i) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BIST unknown/high-Z at simulation time %.1f\n", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
        Q_d = {numIOBit{1'bx}};
        xMemoryAll;
    end
end

always @(CLK_i) begin
    if (CLK_i === 1'b1) begin
        read_flag=0;
        idle_flag=1;
        write_flag=0;
    end
    if (slp_mode === 0 && !SD_i && !DSLP_i && !SLP_i) begin
        if ((CLK_i === 1'bx || CLK_i === 1'bz) && !SD_i && !DSLP_i && !SLP_i) begin
`ifdef no_warning
`else
            $display("\tWarning %m : input CLK unknown/high-Z at simulation time %.1f\n", $realtime);
`endif
`ifdef UNIT_DELAY
            #(SRAM_DELAY);
`endif
            Q_d = {numIOBit{1'bx}};
            xMemoryAll;
        end
        else if ((CLK_i===1) &&(clk_latch===0) && !SD_i && !DSLP_i && !SLP_i && BIST_i !== 1'bx) begin    //posedge
            iRowAddr = iA[numWordAddr-1:numCMAddr];
            iColAddr = iA[numCMAddr-1:0];
            if (iCEB === 1'b0) begin
                idle_flag = 0;
                if (iWEB === 1'b1) begin        // read
                    if (AWT_i === 1'b1) begin
`ifdef no_warning
`else
                        $display("\tWarning %m : Read operation failed when AWT is asserted at simulation time %.1f\n", $realtime);
`endif                        
`ifdef UNIT_DELAY
                        #(SRAM_DELAY);
`endif
                        Q_awt = {numIOBit{1'bx}};
                    end
                    else if (AWT_i === 1'b0) begin
                        read_flag = 1;
                        if ( ^iA === 1'bx ) begin
`ifdef no_warning
`else
                            $display("\tWarning %m : input A/AM unknown/high-Z in read cycle at simulation time %.1f\n", $realtime);
`endif
`ifdef UNIT_DELAY
                            #(SRAM_DELAY);
`endif
                            Q_d = {numIOBit{1'bx}};
                        //xMemoryAll;
                        end 
                        else if (iA >= numWord) begin
`ifdef no_warning
`else
                            $display("\tWarning %m : address exceed word depth in read cycle at simulation time %.1f\n", $realtime);
`endif
`ifdef UNIT_DELAY
                            #(SRAM_DELAY);
`endif
                            Q_d = {numIOBit{1'bx}};
                        end
                        else begin
`ifdef UNIT_DELAY
                            #(SRAM_DELAY);
    `ifdef TSMC_INITIALIZE_FAULT
                            Q_d = (MEMORY[iRowAddr][iColAddr] ^ MEMORY_FAULT[iRowAddr][iColAddr]);
    `else
                            Q_d =  MEMORY[iRowAddr][iColAddr];
    `endif
`else
  `ifdef TSMC_INITIALIZE_FAULT
                            Q_d = {numBit{1'bx}};    //transition to x first
                            #0.001 Q_d = (MEMORY[iRowAddr][iColAddr] ^ MEMORY_FAULT[iRowAddr][iColAddr]);
  `else
                            Q_d = {numBit{1'bx}};    //transition to x first
                            #0.001 Q_d =  MEMORY[iRowAddr][iColAddr];
  `endif
`endif
                        end // else: !if(iA >= numWord)
                    end // AWT_i === 1'b0
                end // if (iWEB === 1'b1)
                else if (iWEB === 1'b0) begin    // write
                    if ( ^iA === 1'bx ) begin
`ifdef no_warning
`else
                        $display("\tWarning %m : input A/AM unknown/high-Z in write cycle at simulation time %.1f\n", $realtime);
`endif
                        xMemoryAll;
                    end 
                    else if (iA >= numWord) begin
`ifdef no_warning
`else
                        $display("\tWarning %m : address exceed word depth in write cycle at simulation time %.1f\n", $realtime);
`endif
                    end 
                    else begin
                        if ( ^iD === 1'bx ) begin
`ifdef no_warning
`else
                            $display("\tWarning %m : input D/DM unknown/high-Z in write cycle at simulation time %.1f\n", $realtime);
`endif
                        end
                        if ( ^iBWEB === 1'bx ) begin
`ifdef no_warning
`else
                            $display("\tWarning %m : input BWEB/BWEBM unknown/high-Z in write cycle at simulation time %.1f\n", $realtime);
`endif
                        end
                        write_flag = 1;
                        begin
                            DIN_tmp = MEMORY[iRowAddr][iColAddr];
                            for (i = 0; i < numBit; i = i + 1) begin
                                if (iBWEB[i] === 1'b0) begin
                                    DIN_tmp[i] = iD[i];
                                end 
                                else if (iBWEB[i] === 1'bx) begin
                                    DIN_tmp[i] = 1'bx;
                                end
                            end
                            if ( isStuckAt0(iA) || isStuckAt1(iA) ) begin
                                combineErrors(iA, ERR_tmp);
                                for (j = 0; j < numBit; j = j + 1) begin
                                    if (ERR_tmp[j] === 1'b0) begin
                                        DIN_tmp[j] = 1'b0;
                                    end 
                                    else if (ERR_tmp[j] === 1'b1) begin
                                        DIN_tmp[j] = 1'b1;
                                    end
                                end
                            end
                            MEMORY[iRowAddr][iColAddr] = DIN_tmp;
                        end
                    end //end of if ( ^iA === 1'bx ) begin
                end 
                else begin
`ifdef no_warning
`else
                    $display("\tWarning %m : input WEB/WEBM unknown/high-Z at simulation time %.1f\n", $realtime);
`endif
`ifdef UNIT_DELAY
                    #(SRAM_DELAY);
`endif
                    Q_d = {numIOBit{1'bx}};
                    xMemoryAll;
                end // else: !if(iWEB === 1'b0)
            end // if (iCEB === 1'b0)
            else if (iCEB === 1'b1) begin
                idle_flag = 1;
            end
            else begin    //CEB is 'x / 'Z                
`ifdef no_warning
`else
                $display("\tWarning %m : input CEB/CEBM unknown/high-Z at simulation time %.1f\n", $realtime);
`endif
`ifdef UNIT_DELAY
                #(SRAM_DELAY);
`endif
                Q_d = {numIOBit{1'bx}};
                xMemoryAll;
            end // else: !if(iCEB === 1'b1)
        end // if ((CLK_i===1) &&(clk_latch===0))
    end
    clk_latch=CLK_i;    //latch CLK_i
end // always @ (CLK_i)




always @(posedge CLK_i) begin
    if (CLK_i === 1'b1) begin
        CEBL = iCEB;
        WEBL = iWEB;
    end
end

always @(SD_i or DSLP_i or SLP_i) begin
    //---- Check SD Unknown
    if ((SD_i === 1'bx || SD_i === 1'bz) && $realtime !=0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input SD unknown/high-Z at simulation time %.1f\n", $realtime);
`endif
        slp_mode=0;
        dslp_mode=0;
        sd_mode=0;
`ifdef UNIT_DELAY
        #(SRAM_DELAY);
`endif
        Q_d={numIOBit{1'bx}};
        xMemoryAll;
    end  //  End Check SD Unknown
    //---- When entering SD mode, check if CEB is asserted or not
    else if (SLP_i===0 && DSLP_i === 0 && SD_i===1 && iCEB!==1'b1 && (sd_mode === 0)) begin
`ifdef no_warning
`else
        $display("\tWarning %m : Invalid Shut Down Mode Sequence. Input CEB 0/unknown/high-Z while entering shut down mode at simulation time %.1f", $realtime);
`endif
        slp_mode=0;
        dslp_mode=0;
        sd_mode=0;
`ifdef UNIT_DELAY
        #(SRAM_DELAY);
`endif
        Q_d={numIOBit{1'bx}};
        xMemoryAll;
    end  //  End When entering SD mode, check if CEB is asserted or not
    //---- When SD wake up, check if CEB is asserted or not
    else if ((SD_i===0  && DSLP_i === 0 && SLP_i === 0 ) && (iCEB!==1)) begin
`ifdef no_warning
`else
        if ($realtime > 0) $display("\tWarning %m : Invalid Wake Up Sequence. Input CEB is 0/unknown/high-Z while exiting shut down mode at simulation time %.1f", $realtime);
`endif
        slp_mode=0;
        dslp_mode=0;
        sd_mode=0;
`ifdef UNIT_DELAY
        #(SRAM_DELAY);
`endif
        Q_d={numIOBit{1'bx}};
        xMemoryAll;
    end  //  End When SD wake up, check if CEB is asserted or not
    //---- Power-Down Mode wake up
    else if ((SD_i===0) && (iCEB===1) && (sd_mode === 1)) begin
	sd_mode = 0;
        if(DSLP_i===0)
            dslp_mode=0;
        if(SLP_i===0)
            slp_mode=0;
        if(DSLP_i===1)
            dslp_mode=1;
        if(SLP_i===1)
            slp_mode=1;
        if(!(slp_mode === 1 || dslp_mode === 1)) begin
`ifdef UNIT_DELAY
            #(SRAM_DELAY);
`endif
            Q_d={numIOBit{1'bx}};
        end
    end  //  End Power-Down Mode wake up
    //---- Entering SD mode
    else if ((SD_i===1) && (iCEB===1) &&  (sd_mode === 0)) begin
        xMemoryAll;
        sd_mode = 1;
        if(DSLP_i===0)
            dslp_mode=0;
        if(SLP_i===0)
            slp_mode=0;
        if(DSLP_i===1)
            dslp_mode=1;
        if(SLP_i===1)
            slp_mode=1;
        if(|Q_d !== 1'b0 || !(slp_mode === 1 || dslp_mode === 1)) begin
`ifdef UNIT_DELAY
            #(SRAM_DELAY);
`endif
            Q_d={numIOBit{1'bx}};
            #0.001;
        end
        Q_d=0;
    end  //  End Entering SD mode
    //---- sd_mode initialization
    else if (sd_mode === 1'bx) begin
      sd_mode = SD_i;
    end  //  End sd_mode initialization
    if (SD_i === 1) begin
        xMemoryAll;   
    end
    //---- Check DSLP Unknown
    else if ((DSLP_i === 1'bx || DSLP_i === 1'bz) && (SD_i===0)  && $realtime !=0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DSLP unknown/high-Z at simulation time %.1f\n", $realtime);
`endif
        slp_mode=0;
        dslp_mode=0;
        sd_mode=0;
`ifdef UNIT_DELAY
        #(SRAM_DELAY);
`endif
        Q_d={numIOBit{1'bx}};
        xMemoryAll;
    end  //  End Check DSLP Unknown
    //---- When entering DSLP mode, check if CEB is asserted or not
    else if (SD_i === 0 && DSLP_i===1 && SLP_i===0 && iCEB!==1'b1 && (dslp_mode === 0) ) begin
`ifdef no_warning
`else
        $display("\tWarning %m : Invalid Deep Sleep Mode Sequence. Input CEB 0/unknown/high-Z while entering deep sleep mode at simulation time %.1f", $realtime);
`endif
        slp_mode=0;
        dslp_mode=0;
        sd_mode=0;
`ifdef UNIT_DELAY
        #(SRAM_DELAY);
`endif
        Q_d={numIOBit{1'bx}};
        xMemoryAll;
    end  //  End When entering DSLP mode, check if CEB is asserted or not
    //---- When DSLP wake up, check if CEB is asserted or not
    else if ((SD_i === 0 && DSLP_i===0 && SLP_i===0) && (iCEB!==1) && (dslp_mode === 1)) begin
`ifdef no_warning
`else
        if ($realtime > 0) $display("\tWarning %m : Invalid Wake Up Sequence. Input CEB is 0/unknown/high-Z while exiting deep sleep mode at simulation time %.1f", $realtime);
`endif
        slp_mode=0;
        dslp_mode=0;
        sd_mode=0;
`ifdef UNIT_DELAY
        #(SRAM_DELAY);
`endif
        Q_d={numIOBit{1'bx}};
        xMemoryAll;
    end  //  End When DSLP wake up, check if CEB is asserted or not
    //---- DSLP Wake up
    else if ((DSLP_i===0) && (iCEB===1) && (dslp_mode === 1)) begin
        dslp_mode=0;
        if(!(sd_mode === 1 || slp_mode === 1)) begin
            Q_d={numIOBit{1'bx}};
        end
    end  //  End DSLP wake up
    //---- Entering DSLP mode
    else if ((DSLP_i===1) && (iCEB===1) &&  (dslp_mode === 0)) begin
        dslp_mode=1;
        if(SLP_i===0)
            slp_mode=0;
        if(SLP_i===1)
            slp_mode=1;
        if(|Q_d !== 1'b0 || !(sd_mode === 1 || slp_mode === 1)) begin
`ifdef UNIT_DELAY
            #(SRAM_DELAY);
`endif
            Q_d={numIOBit{1'bx}};
            #0.001;
        end
        Q_d=0;
    end  //  End Entering DSLP mode
    //---- dslp_mode initialization
    else if (dslp_mode === 1'bx) begin
      dslp_mode = DSLP_i;
    end  //  End dslp_mode initialization
    //---- Check SLP Unknown
    else if ((SLP_i === 1'bx || SLP_i === 1'bz) && (DSLP_i===0) && (SD_i===0) && $realtime !=0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input SLP unknown/high-Z at simulation time %.1f\n", $realtime);
`endif
        slp_mode=0;
        dslp_mode=0;
        sd_mode=0;
`ifdef UNIT_DELAY
        #(SRAM_DELAY);
`endif
        Q_d={numIOBit{1'bx}};
        xMemoryAll;
    end  //  End Check SLP Unknown
    //---- When entering SLP mode, check if CEB is asserted or not
    else if (SD_i === 0 && DSLP_i===0 && SLP_i===1 && iCEB!==1'b1 && (slp_mode === 0)) begin
`ifdef no_warning
`else
        $display("\tWarning %m : Invalid Sleep Mode Sequence. Input CEB 0/unknown/high-Z while entering sleep mode at simulation time %.1f", $realtime);
`endif
        slp_mode=0;
        dslp_mode=0;
        sd_mode=0;
`ifdef UNIT_DELAY
        #(SRAM_DELAY);
`endif
        Q_d={numIOBit{1'bx}};
        xMemoryAll;
    end  //  End When entering SLP mode, check if CEB is asserted or not
    //---- When SLP wake up, check if CEB is asserted or not
    else if ((SLP_i===0 && DSLP_i===0 && SLP_i===0) && (iCEB!==1) && (slp_mode === 1)) begin
`ifdef no_warning
`else
        if ($realtime > 0) $display("\tWarning %m : Invalid Wake Up Sequence. Input CEB is 0/unknown/high-Z while exiting sleep mode at simulation time %.1f", $realtime);
`endif
        slp_mode=0;
        dslp_mode=0;
        sd_mode=0;
`ifdef UNIT_DELAY
        #(SRAM_DELAY);
`endif
        Q_d={numIOBit{1'bx}};
        xMemoryAll;
    end   //  End When SLP wake up, check if CEB is asserted or not
    //---- SLP Wake up
    else if ((SLP_i===0) && (iCEB===1) && (slp_mode === 1)) begin
        slp_mode=0;
        if(!(sd_mode === 1 || dslp_mode === 1)) begin
            Q_d={numIOBit{1'bx}};
        end
    end  //  End SLP wake up
    //---- Entering SLP mode
    else if ((SLP_i===1) && (iCEB===1) &&  (slp_mode === 0)) begin
        slp_mode=1;
        if(!(sd_mode === 1 || dslp_mode === 1)) begin
`ifdef UNIT_DELAY
            #(SRAM_DELAY);
`endif
            Q_d={numIOBit{1'bx}};
            #0.001;
        end
        Q_d=0;
    end  //  End Entering SLP mode
    //---- slp_mode initialization
    else if (slp_mode === 1'bx) begin
      slp_mode = SLP_i;
    end  //  End slp_mode initialization
end

always @(negedge AWT_i) begin
    if( !SD_i && !DSLP_i && !SLP_i) begin
        Q_d = {numIOBit{1'bx}};
        Q_awt = {numIOBit{1'bx}};
    end
end

always @(AWT_i) begin
    if(AWT_i===1 && !SD_i && !DSLP_i && !SLP_i) begin
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`else
        Q_d={numIOBit{1'bx}};
`endif
    end
    else if ((AWT_i === 1'bx || AWT_i === 1'bz) && !SD_i && !DSLP_i && !SLP_i) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AWT unknown/high-Z at simulation time %.1f\n", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
        Q_d={numIOBit{1'bx}};
    end
end

always @(negedge SD_i) begin
    if (SLP_i === 1'b0 && DSLP_i === 1'b0 && SD_i === 1'b0) begin
        if(AWT_i === 1'b1) begin
`ifdef no_warning
`else
            $display("\tWarning %m : AWT function will not be activated during wake up time at simulation time %.1f\n", $realtime);
`endif        
            Q_awt = {numIOBit{1'bx}};
            Q_d = {numIOBit{1'bx}};
        end
    end
end
always @(negedge SLP_i) begin
    if (SLP_i === 1'b0 && DSLP_i === 1'b0 && SD_i === 1'b0) begin
        if(AWT_i === 1'b1) begin
`ifdef no_warning
`else
            $display("\tWarning %m : AWT function will not be activated during wake up time at simulation time %.1f\n", $realtime);
`endif        
            Q_awt = {numIOBit{1'bx}};
            Q_d = {numIOBit{1'bx}};
        end
    end
end

always @(iD or iBWEB or read_flag or AWT_i) begin : AWTQ
    if(read_flag===1 && AWT_i && !SD_i && !DSLP_i && !SLP_i) begin
`ifdef no_warning
`else
        $display("\tWarning %m : Read operation failed when AWT is asserted at simulation time %.1f\n", $realtime);
`endif
`ifdef UNIT_DELAY
        #(SRAM_DELAY);
`endif
        Q_awt = {numIOBit{1'bx}};
    end
    else if(read_flag===0 && !(CEBL === 1'b0 && WEBL === 1'b1) && AWT_i && !SD_i && !DSLP_i && !SLP_i) begin
`ifdef UNIT_DELAY
        Q_awt = Q_d;
        #(SRAM_DELAY);
`else
        Q_awt = {numIOBit{1'bx}};
        #0.001;
`endif
        Q_awt = iD ^ iBWEB;
    end
end

always @(posedge SD_i or posedge DSLP_i or posedge SLP_i) begin
    if (SD_i === 1'b1 && SLP === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input SLP high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BIST === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BIST high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BIST === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BIST high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BIST === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BIST high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && CEB === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CEB high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && CEB === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CEB high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && CEB === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CEB high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && WEB === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input WEB high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && WEB === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input WEB high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && WEB === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input WEB high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[0] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[0] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[0] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[1] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[1] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[1] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[2] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[2] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[2] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[3] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[3] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[3] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[4] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[4] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[4] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[5] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[5] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[5] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[6] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[6] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[6] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[6] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[6] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[6] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[7] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[7] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[7] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[7] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[7] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[7] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[8] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[8] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[8] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[8] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[8] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[8] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[9] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[9] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[9] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[9] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[9] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[9] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[10] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[10] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[10] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[10] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[10] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[10] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[11] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[11] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[11] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[11] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[11] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[11] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[12] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[12] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && A[12] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[12] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && A[12] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[12] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[0] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEB[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[0] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEB[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[0] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[1] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEB[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[1] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEB[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[1] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[2] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEB[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[2] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEB[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[2] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[3] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEB[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[3] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEB[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[3] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[4] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEB[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[4] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEB[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[4] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[5] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEB[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[5] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEB[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[5] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[0] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && D[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[0] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && D[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[0] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[1] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && D[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[1] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && D[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[1] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[2] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && D[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[2] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && D[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[2] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[3] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && D[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[3] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && D[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[3] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[4] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && D[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[4] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && D[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[4] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[5] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && D[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[5] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && D[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[5] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && CEBM === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CEBM high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && CEBM === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CEBM high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && CEBM === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CEBM high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && WEBM === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input WEBM high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && WEBM === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input WEBM high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && WEBM === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input WEBM high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[0] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[0] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[0] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[1] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[1] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[1] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[2] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[2] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[2] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[3] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[3] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[3] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[4] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[4] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[4] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[5] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[5] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[5] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[6] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[6] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[6] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[6] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[6] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[6] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[7] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[7] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[7] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[7] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[7] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[7] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[8] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[8] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[8] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[8] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[8] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[8] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[9] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[9] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[9] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[9] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[9] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[9] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[10] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[10] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[10] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[10] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[10] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[10] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[11] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[11] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[11] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[11] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[11] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[11] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[12] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[12] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AM[12] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[12] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AM[12] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[12] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[0] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEBM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[0] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEBM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[0] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[1] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEBM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[1] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEBM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[1] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[2] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEBM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[2] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEBM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[2] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[3] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEBM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[3] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEBM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[3] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[4] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEBM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[4] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEBM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[4] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[5] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && BWEBM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[5] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && BWEBM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[5] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[0] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && DM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[0] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && DM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[0] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[1] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && DM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[1] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && DM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[1] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[2] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && DM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[2] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && DM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[2] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[3] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && DM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[3] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && DM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[3] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[4] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && DM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[4] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && DM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[4] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[5] high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && DM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[5] high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && DM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[5] high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && CLK === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CLK high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && CLK === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CLK high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && CLK === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CLK high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b1 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AWT === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AWT high-Z during Shut Down Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b1 && SLP_i === 1'b0 && AWT === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AWT high-Z during DSLP Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    else if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b1 && AWT === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AWT high-Z during Sleep Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
end
always @(negedge SD_i or negedge DSLP_i or negedge SLP_i) begin
    if (SD_i === 1'b1 && SLP === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input SLP high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BIST === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BIST high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && CEB === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CEB high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && WEB === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input WEB high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[0] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[1] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[2] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[3] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[4] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[5] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[6] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[6] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[7] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[7] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[8] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[8] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[9] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[9] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[10] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[10] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[11] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[11] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && A[12] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input A[12] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[0] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[1] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[2] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[3] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[4] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEB[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEB[5] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[0] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[0] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[1] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[1] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[2] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[2] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[3] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[3] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[4] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[4] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && D[5] === 1'bz && BIST_i !== 1'b1) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input D[5] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && CEBM === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CEBM high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && WEBM === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input WEBM high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[0] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[1] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[2] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[3] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[4] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[5] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[6] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[6] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[7] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[7] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[8] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[8] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[9] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[9] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[10] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[10] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[11] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[11] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AM[12] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AM[12] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[0] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[1] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[2] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[3] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[4] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && BWEBM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input BWEBM[5] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[0] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[0] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[1] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[1] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[2] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[2] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[3] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[3] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[4] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[4] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && DM[5] === 1'bz && BIST_i !== 1'b0) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input DM[5] high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end

    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && CLK === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input CLK high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
    if (SD_i === 1'b0 && DSLP_i === 1'b0 && SLP_i === 1'b0 && AWT === 1'bz) begin
`ifdef no_warning
`else
        $display("\tWarning %m : input AWT high-Z during Wake Up Mode, Core Unknown at %t.>>", $realtime);
`endif
`ifdef UNIT_DELAY
    #(SRAM_DELAY);
`endif
      Q_d = {numIOBit{1'bx}};
      xMemoryAll;
    end
end

`ifdef UNIT_DELAY
`else
always @(notify_sd) begin
    Q_d = {numIOBit{1'bx}};
    xMemoryAll;
end
always @(notify_slp) begin
    Q_d = {numIOBit{1'bx}};
    xMemoryAll;
end

always @(notify_awt_sd) begin
    disable AWTQ;
    Q_d = {numIOBit{1'bx}};
    Q_awt = {numIOBit{1'bx}};
end
always @(notify_awt_slp) begin
    disable AWTQ;
    Q_d = {numIOBit{1'bx}};
    Q_awt = {numIOBit{1'bx}};
end

always @(notify_clk) begin
    Q_d = {numIOBit{1'bx}};
    xMemoryAll;
end
always @(notify_bist) begin
    Q_d = {numIOBit{1'bx}};
    xMemoryAll;
end
always @(notify_ceb) begin
    Q_d = {numIOBit{1'bx}};
    xMemoryAll;
    read_flag = 0;
    write_flag = 0;
end
always @(notify_web) begin
    Q_d = {numIOBit{1'bx}};
    xMemoryAll;
    read_flag = 0;
    write_flag = 0;
end
always @(notify_addr) begin
    if (iWEB === 1'b1) begin
        Q_d = {numIOBit{1'bx}};
    end
    else if (iWEB === 1'b0) begin
        xMemoryAll;
    end
    else begin
        Q_d = {numIOBit{1'bx}};
    xMemoryAll;
    end
    read_flag = 0;
    write_flag = 0;
end
always @(notify_din) begin
    if ( ^iA === 1'bx ) begin
        xMemoryAll;
    end
    else begin
        xMemoryWord(iA);
    end
    write_flag = 0;
end
always @(notify_bweb) begin
    if ( ^iA === 1'bx ) begin
        xMemoryAll;
    end
    else begin
        xMemoryWord(iA);
    end
    write_flag = 0;
end

`endif    //end `ifdef UNIT_DELAY


task xMemoryAll;
reg [numRowAddr-1:0] row;
reg [numCMAddr-1:0] col;
reg [numRowAddr:0] row_index;
reg [numCMAddr:0] col_index;
begin
    for (row_index = 0; row_index <= numRow-1; row_index = row_index + 1) begin
        for (col_index = 0; col_index <= numCM-1; col_index = col_index + 1) begin
            row=row_index;
            col=col_index;
            MEMORY[row][col] = {numBit{1'bx}};
        end
    end
end
endtask

task zeroMemoryAll;
reg [numRowAddr-1:0] row;
reg [numCMAddr-1:0] col;
reg [numRowAddr:0] row_index;
reg [numCMAddr:0] col_index;
begin
    for (row_index = 0; row_index <= numRow-1; row_index = row_index + 1) begin
        for (col_index = 0; col_index <= numCM-1; col_index = col_index + 1) begin
            row=row_index;
            col=col_index;
            MEMORY[row][col] = {numBit{1'b0}};
        end
    end
end
endtask

task xMemoryWord;
input [numWordAddr-1:0] addr;
reg [numRowAddr-1:0] row;
reg [numCMAddr-1:0] col;
begin
    {row, col} = addr;
    MEMORY[row][col] = {numBit{1'bx}};
end
endtask

task preloadData;
input [256*8:1] infile;  // Max 256 character File Name
reg [numWordAddr:0] w;
reg [numWordAddr-numCMAddr-1:0] row;
reg [numCMAddr-1:0] col;
begin
`ifdef no_warning
`else
    $display("Preloading data from file %s", infile);
`endif
`ifdef TSMC_INITIALIZE_FORMAT_BINARY
        $readmemb(infile, PRELOAD);
`else
        $readmemh(infile, PRELOAD);
`endif
    for (w = 0; w < numWord; w = w + 1) begin
        {row, col} = w;
        {row, col} = w;
        MEMORY[row][col] = PRELOAD[w];
    end
end
endtask

/*
 * task injectSA - to inject a stuck-at error, please use hierarchical reference to call the injectSA task from the wrapper module
 *      input addr - the address location where the defect is to be introduced
 *      input bit - the bit location of the specified address where the defect is to occur
 *      input type - specify whether it's a s-a-0 (type = 0) or a s-a-1 (type = 1) fault
 *
 *      Multiple faults can be injected at the same address, regardless of the type.  This means that an address location can have 
 *      certain bits having stuck-at-0 faults while other bits have the stuck-at-1 defect.
 *
 * Examples:
 *      injectSA(0, 0, 0);  - injects a s-a-0 fault at address 0, bit 0
 *      injectSA(1, 0, 1);  - injects a s-a-1 fault at address 1, bit 0
 *      injectSA(1, 1, 0);  - injects a s-a-0 fault at address 1, bit 1
 *      injectSA(1, 2, 1);  - injects a s-a-1 fault at address 1, bit 2
 *      injectSA(1, 3, 1);  - injects a s-a-1 fault at address 1, bit 3
 *      injectSA(2, 2, 1);  - injects a s-a-1 fault at address 2, bit 2
 *      injectSA(14, 2, 0); - injects a s-a-0 fault at address 14, bit 2
 *
 */
task injectSA;
input [numWordAddr-1:0] addr;
input integer bitn;
input typen;
reg [numStuckAt:0] i;
reg [numBit-1:0] btmp;
begin
    j=bitn;
    if ( typen === 0 ) begin
        for (i = 0; i < numStuckAt; i = i + 1) begin
            if ( ^stuckAt0Addr[i] === 1'bx ) begin
                stuckAt0Addr[i] = addr;
                btmp = {numBit{1'bx}};
                btmp[j] = 1'b0;
                stuckAt0Bit[i] = btmp;
                i = numStuckAt;
`ifdef no_warning
`else
                $display("First s-a-0 error injected at address location %d = %b", addr, btmp);
`endif
                i = numStuckAt;
            end
            else if ( stuckAt0Addr[i] === addr ) begin
                btmp = stuckAt0Bit[i];
                btmp[j] = 1'b0;
                stuckAt0Bit[i] = btmp;
`ifdef no_warning
`else
                $display("More s-a-0 Error injected at address location %d = %b", addr, btmp);
`endif
                i = numStuckAt;
            end        
        end
    end
    else if (typen === 1) begin
        for (i = 0; i < numStuckAt; i = i + 1) begin
            if ( ^stuckAt1Addr[i] === 1'bx ) begin
                stuckAt1Addr[i] = addr;
                btmp = {numBit{1'bx}};
                btmp[j] = 1'b1;
                stuckAt1Bit[i] = btmp;
                i = numStuckAt;
`ifdef no_warning
`else
                $display("First s-a-1 error injected at address location %d = %b", addr, btmp);
`endif
                i = numStuckAt;
            end
            else if ( stuckAt1Addr[i] === addr ) begin
                btmp = stuckAt1Bit[i];
                btmp[j] = 1'b1;
                stuckAt1Bit[i] = btmp;
`ifdef no_warning
`else
                $display("More s-a-1 Error injected at address location %d = %b", addr, btmp);
`endif
                i = numStuckAt;
            end        
        end
    end
end
endtask

task combineErrors;
input [numWordAddr-1:0] addr;
output [numBit-1:0] errors;
integer j;
reg [numBit-1:0] btmp;
begin
    errors = {numBit{1'bx}};
    if ( isStuckAt0(addr) ) begin
        btmp = stuckAt0Bit[getStuckAt0Index(addr)];
        for ( j = 0; j < numBit; j = j + 1 ) begin
            if ( btmp[j] === 1'b0 ) begin
                errors[j] = 1'b0;
            end
        end
    end
    if ( isStuckAt1(addr) ) begin
        btmp = stuckAt1Bit[getStuckAt1Index(addr)];
        for ( j = 0; j < numBit; j = j + 1 ) begin
            if ( btmp[j] === 1'b1 ) begin
                errors[j] = 1'b1;
            end
        end
    end
end
endtask

function [numStuckAt-1:0] getStuckAt0Index;
input [numWordAddr-1:0] addr;
reg [numStuckAt:0] i;
begin
    for (i = 0; i < numStuckAt; i = i + 1) begin
        if (stuckAt0Addr[i] === addr) begin
            getStuckAt0Index = i;
        end
    end
end
endfunction

function [numStuckAt-1:0] getStuckAt1Index;
input [numWordAddr-1:0] addr;
reg [numStuckAt:0] i;
begin
    for (i = 0; i < numStuckAt; i = i + 1) begin
        if (stuckAt1Addr[i] === addr) begin
            getStuckAt1Index = i;
        end
    end
end
endfunction

function isStuckAt0;
input [numWordAddr-1:0] addr;
reg [numStuckAt:0] i;
reg flag;
begin
    flag = 0;
    for (i = 0; i < numStuckAt; i = i + 1) begin
        if (stuckAt0Addr[i] === addr) begin
            flag = 1;
            i = numStuckAt;
        end
    end
    isStuckAt0 = flag;
end
endfunction


function isStuckAt1;
input [numWordAddr-1:0] addr;
reg [numStuckAt:0] i;
reg flag;
begin
    flag = 0;
    for (i = 0; i < numStuckAt; i = i + 1) begin
        if (stuckAt1Addr[i] === addr) begin
            flag = 1;
            i = numStuckAt;
        end
    end
    isStuckAt1 = flag;
end
endfunction

task printMemory;
reg [numRowAddr-1:0] row;
reg [numCMAddr-1:0] col;
reg [numRowAddr:0] row_index;
reg [numCMAddr:0] col_index;
reg [numBit-1:0] temp;
begin
    $display("\n\nDumping memory content at %.1f...\n", $realtime);
    for (row_index = 0; row_index <= numRow-1; row_index = row_index + 1) begin
        for (col_index = 0; col_index <= numCM-1; col_index = col_index + 1) begin
             row=row_index;
            col=col_index;
            $display("[%d] = %b", {row, col}, MEMORY[row][col]);
        end
    end    
    $display("\n\n");
end
endtask

task printMemoryFromTo;
input [numWordAddr-1:0] addr1;
input [numWordAddr-1:0] addr2;
reg [numWordAddr:0] addr;
reg [numRowAddr-1:0] row;
reg [numCMAddr-1:0] col;
reg [numBit-1:0] temp;
begin
    $display("\n\nDumping memory content at %.1f...\n", $realtime);
    for (addr = addr1; addr < addr2; addr = addr + 1) begin
        {row, col} = addr;
        $display("[%d] = %b", addr, MEMORY[row][col]);
    end    
    $display("\n\n");
end
endtask


endmodule
`endcelldefine
