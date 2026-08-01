// Source        : SCRUBD-CD (MSR 2025)
// Contract addr : 0xbaf51e761510c1a11bf48dd87c0307ac8a8c8a4f
// Target fn     : ETH_VAULT.CashOut
// Original pragma: pragma solidity ^0.4.19;
// Original LOC  : 70
// Sub-contracts : 2 (ETH_VAULT, Log)
// Port report   : {"pragma_changed": true, "call_value_replaced": 1, "now_replaced": 1, "unnamed_fn_replaced": 1, "constructor_replaced": 1}

// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract ETH_VAULT
{
    mapping (address => uint) public balances;

    uint public MinDeposit = 1 ether;

    Log TransferLog;

    constructor(address _log) {
        TransferLog = Log(_log);
    }

    function Deposit()
    public
    payable
    {
        if(msg.value > MinDeposit)
        {
            balances[msg.sender]+=msg.value;
            TransferLog.AddMessage(msg.sender,msg.value,"Deposit");
        }
    }

    function CashOut(uint _am)
    public
    payable
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
