// Source        : SCRUBD-CD (MSR 2025)
// Contract addr : 0x463f235748bc7862deaa04d85b4b16ac8fafef39
// Target fn     : PrivateBank.CashOut
// Original pragma: pragma solidity ^0.4.19;
// Original LOC  : 74
// Sub-contracts : 2 (PrivateBank, Log)
// Port report   : {"pragma_changed": true, "call_value_replaced": 1, "now_replaced": 1, "unnamed_fn_replaced": 1, "constructor_replaced": 1}
//
// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract PrivateBank
{
    mapping (address => uint) balances;
    
    function GetBal() 
    public
    returns (uint) 
    {
        return balances[msg.sender];
    }
    
    uint public MinDeposit = 1 ether;
    
    Log TransferLog;
    
    constructor(address _lib)
    {
        TransferLog = Log(_lib);
    }
    
    function Deposit()
    public
    payable
    {
        if(msg.value >= MinDeposit)
        {
            balances[msg.sender]+=msg.value;
            TransferLog.AddMessage(msg.sender,msg.value,"Deposit");
        }
    }
    
    function CashOut(uint _am) public
    {
        if(_am<=balances[msg.sender])
        {
            
            (bool _callOk1, ) = msg.sender.call{value: _am}("");

            
            if (_callOk1)
            {
                balances[msg.sender]-=_am;
                TransferLog.AddMessage(msg.sender,_am,"CashOut");
            }
        }
    }
    
    receive() external payable {}    
    
}

contract Log 
{
   
    struct Message
    {
        address Sender;
        string  Data;
        uint Val;
        uint  Time;
    }
    
    Message[] public History;
    
    Message LastMsg;
    
    function AddMessage(address _adr,uint _val,string memory _data)
    public
    {
        LastMsg.Sender = _adr;
        LastMsg.Time = block.timestamp;
        LastMsg.Val = _val;
        LastMsg.Data = _data;
        History.push(LastMsg);
    }
}